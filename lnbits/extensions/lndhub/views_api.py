import time
from base64 import urlsafe_b64encode
from flask import jsonify, g, request

from lnbits.core.services import pay_invoice, create_invoice
from lnbits.decorators import api_validate_post_request
from lnbits import bolt11

from lnbits.extensions.lndhub import lndhub_ext
from .decorators import check_wallet
from .utils import to_buffer, decoded_as_lndhub


@lndhub_ext.route("/ext/getinfo", methods=["GET"])
def lndhub_getinfo():
    return jsonify({"error": True, "code": 1, "message": "bad auth"})


@lndhub_ext.route("/ext/auth", methods=["POST"])
@api_validate_post_request(
    schema={
        "login": {"type": "string", "required": True, "excludes": "refresh_token"},
        "password": {"type": "string", "required": True, "excludes": "refresh_token"},
        "refresh_token": {"type": "string", "required": True, "excludes": ["login", "password"]},
    }
)
def lndhub_auth():
    token = (
        g.data["token"]
        if "token" in g.data and g.data["token"]
        else urlsafe_b64encode((g.data["login"] + ":" + g.data["password"]).encode("utf-8")).decode("ascii")
    )
    return jsonify({"refresh_token": token, "access_token": token})


@lndhub_ext.route("/ext/addinvoice", methods=["POST"])
@check_wallet()
@api_validate_post_request(
    schema={
        "amt": {"type": "string", "required": True},
        "memo": {"type": "string", "required": True},
        "preimage": {"type": "string", "required": False},
    }
)
def lndhub_addinvoice():
    try:
        _, pr = create_invoice(wallet_id=g.wallet.id, amount=int(g.data["amt"]), memo=g.data["memo"],)
    except Exception as e:
        return jsonify({"error": True, "code": 7, "message": "Failed to create invoice: " + str(e),})

    invoice = bolt11.decode(pr)
    return jsonify(
        {
            "pay_req": pr,
            "payment_request": pr,
            "add_index": "500",
            "r_hash": to_buffer(invoice.payment_hash),
            "hash": invoice.payment_hash,
        }
    )


@lndhub_ext.route("/ext/payinvoice", methods=["POST"])
@check_wallet(requires_admin=True)
@api_validate_post_request(schema={"invoice": {"type": "string", "required": True}})
def lndhub_payinvoice():
    try:
        pay_invoice(wallet_id=g.wallet.id, bolt11=g.data["invoice"])
    except Exception as e:
        return jsonify({"error": True, "code": 10, "message": "Payment failed: " + str(e),})

    invoice = bolt11.decode(g.data["invoice"])
    return jsonify(
        {
            "payment_error": "",
            "payment_preimage": "0" * 64,
            "route": {},
            "payment_hash": invoice.payment_hash,
            "decoded": decoded_as_lndhub(invoice),
            "fee_msat": 0,
            "type": "paid_invoice",
            "fee": 0,
            "value": invoice.amount_msat / 1000,
            "timestamp": int(time.time()),
            "memo": invoice.description,
        }
    )


@lndhub_ext.route("/ext/balance", methods=["GET"])
@check_wallet()
def lndhub_balance():
    return jsonify({"BTC": {"AvailableBalance": g.wallet.balance}})


@lndhub_ext.route("/ext/gettxs", methods=["GET"])
@check_wallet()
def lndhub_gettxs():
    return jsonify(
        [
            {
                "payment_preimage": "0" * 64,
                "payment_hash": "0" * 64,
                "fee_msat": payment.fee * 1000,
                "type": "paid_invoice",
                "fee": payment.fee,
                "value": int(payment.amount / 1000),
                "timestamp": payment.time,
                "memo": payment.memo if not payment.pending else "Payment in transition",
            }
            for payment in g.wallet.get_payments(pending=True, complete=True, outgoing=True, incoming=False)
        ]
    )


@lndhub_ext.route("/ext/getuserinvoices", methods=["GET"])
@check_wallet()
def lndhub_getuserinvoices():
    return jsonify(
        [
            {
                "r_hash": "0" * 64,
                "payment_request": "lnbc1p056vh9pp5wnz467ncg9lfl2s5amfc5xy592097ysgggqfamqu6l93vvxdayzqdqqxqyjw5qcqp2sp5l4yg34fs5hdgswaj2qxc3w8uq4kwvx9nusjq5zsf20draz666ekqrzjq24v2j9cwunecv8n4wahxqw7jvykuwu8z38ufpxuxsymkrtt64ntzzd80qqqg6cqqqqqqquyqqqqqqgqpc9qy9qsqjlhj37tscvnk3j4z6r7u52h87lqjq0faxuapn073djmslpnn6m0y98rdqh9tg8h5dl9fewl8zeaf3ftgwej5p5a9myp342xvlhfgmggq567c49",
                "add_index": "500",
                "description": invoice.memo,
                "payment_hash": "0" * 64,
                "ispaid": not invoice.pending,
                "amt": int(invoice.amount / 1000),
                "expire_time": int(time.time() + 1800),
                "timestamp": invoice.time,
                "type": "user_invoice",
            }
            for invoice in g.wallet.get_payments(pending=True, complete=True, incoming=True, outgoing=False)
        ]
    )


@lndhub_ext.route("/ext/getbtc", methods=["GET"])
@check_wallet()
def lndhub_getbtc():
    "load an address for incoming onchain btc"
    return jsonify([])


@lndhub_ext.route("/ext/getpending", methods=["GET"])
@check_wallet()
def lndhub_getpending():
    "pending onchain transactions"
    return jsonify([])


@lndhub_ext.route("/ext/decodeinvoice", methods=["GET"])
def lndhub_decodeinvoice():
    invoice = request.args.get("invoice")
    inv = bolt11.decode(invoice)
    return jsonify(decoded_as_lndhub(inv))


@lndhub_ext.route("/ext/checkrouteinvoice", methods=["GET"])
def lndhub_checkrouteinvoice():
    "not implemented on canonical lndhub"
    pass
