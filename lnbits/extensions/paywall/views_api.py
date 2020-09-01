from flask import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from lnbits.extensions.paywall import paywall_ext
from .crud import create_paywall, get_paywall, get_paywalls, delete_paywall


@paywall_ext.route("/api/v1/paywalls", methods=["GET"])
@api_check_wallet_key("invoice")
def api_paywalls():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([paywall._asdict() for paywall in get_paywalls(wallet_ids)]), HTTPStatus.OK


@paywall_ext.route("/api/v1/paywalls", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "url": {"type": "string", "empty": False, "required": True},
        "memo": {"type": "string", "empty": False, "required": True},
        "description": {"type": "string", "empty": True, "nullable": True, "required": False},
        "amount": {"type": "integer", "min": 0, "required": True},
        "remembers": {"type": "boolean", "required": True},
    }
)
def api_paywall_create():
    paywall = create_paywall(wallet_id=g.wallet.id, **g.data)

    return jsonify(paywall._asdict()), HTTPStatus.CREATED


@paywall_ext.route("/api/v1/paywalls/<paywall_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_paywall_delete(paywall_id):
    paywall = get_paywall(paywall_id)

    if not paywall:
        return jsonify({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    if paywall.wallet != g.wallet.id:
        return jsonify({"message": "Not your paywall."}), HTTPStatus.FORBIDDEN

    delete_paywall(paywall_id)

    return "", HTTPStatus.NO_CONTENT


@paywall_ext.route("/api/v1/paywalls/<paywall_id>/invoice", methods=["POST"])
@api_validate_post_request(schema={"amount": {"type": "integer", "min": 1, "required": True}})
def api_paywall_create_invoice(paywall_id):
    paywall = get_paywall(paywall_id)

    if g.data["amount"] < paywall.amount:
        return jsonify({"message": f"Minimum amount is {paywall.amount} sat."}), HTTPStatus.BAD_REQUEST

    try:
        amount = g.data["amount"] if g.data["amount"] > paywall.amount else paywall.amount
        payment_hash, payment_request = create_invoice(
            wallet_id=paywall.wallet, amount=amount, memo=f"#paywall {paywall.memo}"
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"payment_hash": payment_hash, "payment_request": payment_request}), HTTPStatus.CREATED


@paywall_ext.route("/api/v1/paywalls/<paywall_id>/check_invoice", methods=["POST"])
@api_validate_post_request(schema={"payment_hash": {"type": "string", "empty": False, "required": True}})
def api_paywal_check_invoice(paywall_id):
    paywall = get_paywall(paywall_id)

    if not paywall:
        return jsonify({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    try:
        is_paid = not check_invoice_status(paywall.wallet, g.data["payment_hash"]).pending
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    if is_paid:
        wallet = get_wallet(paywall.wallet)
        payment = wallet.get_payment(g.data["payment_hash"])
        payment.set_pending(False)

        return jsonify({"paid": True, "url": paywall.url, "remembers": paywall.remembers}), HTTPStatus.OK

    return jsonify({"paid": False}), HTTPStatus.OK
