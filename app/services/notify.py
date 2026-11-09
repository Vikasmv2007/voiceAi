"""Messages to the customer's phone: "order confirmed", "ready for pickup", payment links...

Uses WhatsApp (Meta Cloud API) if WHATSAPP_TOKEN + WHATSAPP_PHONE_NUMBER_ID are set,
otherwise Twilio SMS if TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_SMS_FROM are set,
otherwise nothing is sent. Sending happens in the background, so the dashboard never waits.

WhatsApp note: messages that YOU start must use a pre-approved template. Create one in
Meta Business Manager with a single body variable, e.g.  "{{1}}",  and put its name in
WHATSAPP_TEMPLATE. Without a template, plain text only reaches customers who messaged you
in the last 24 hours.
"""
import re
import threading

import requests

from app import config

GRAPH_URL = "https://graph.facebook.com/v21.0/{}/messages"
TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json"


def whatsapp_on():
    return bool(config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID)


def sms_on():
    return bool(config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_SMS_FROM)


def enabled():
    return whatsapp_on() or sms_on()


def international(phone):
    """'9876543210' -> '919876543210' (digits only, with the country code)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = config.COUNTRY_CODE + digits
    return digits if 11 <= len(digits) <= 15 else None


def _send_whatsapp(to, text):
    if config.WHATSAPP_TEMPLATE:
        body = {"messaging_product": "whatsapp", "to": to, "type": "template",
                "template": {"name": config.WHATSAPP_TEMPLATE, "language": {"code": config.WHATSAPP_TEMPLATE_LANG},
                             "components": [{"type": "body", "parameters": [{"type": "text", "text": text[:1000]}]}]}}
    else:
        body = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:4000]}}
    r = requests.post(GRAPH_URL.format(config.WHATSAPP_PHONE_NUMBER_ID), json=body, timeout=10,
                      headers={"Authorization": "Bearer " + config.WHATSAPP_TOKEN})
    r.raise_for_status()


def _send_sms(to, text):
    r = requests.post(TWILIO_URL.format(config.TWILIO_ACCOUNT_SID), timeout=10,
                      auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
                      data={"From": config.TWILIO_SMS_FROM, "To": "+" + to, "Body": text[:1500]})
    r.raise_for_status()


def _deliver(to, text):
    try:
        if whatsapp_on():
            _send_whatsapp(to, text)
        elif sms_on():
            _send_sms(to, text)
    except Exception as e:                   # a failed message must never break ordering
        print(f"[notify] could not message {to[:4]}******: {type(e).__name__}: {str(e)[:150]}")


def send(phone, text, wait=False):
    """Send in the background. Returns True if a channel is configured and the number looks valid."""
    to = international(phone)
    if not (enabled() and to and text):
        return False
    if wait:
        _deliver(to, text)
    else:
        threading.Thread(target=_deliver, args=(to, text), daemon=True).start()
    return True
