"""
backend.py — ZonaTrialApp
© DanielReal 2026. Todos los derechos reservados.

Servidor puente entre tu app web (HTML/JS) y la Android TV real.

¿Por qué existe esto? Porque el navegador NO puede hablar el protocolo
"Android TV Remote v2" directamente (requiere sockets TLS/TCP crudos, algo
que JavaScript de navegador no tiene permitido por seguridad). Este servidor
sí puede (corre en Python, en tu propia máquina), y expone endpoints HTTP
simples que tu HTML puede llamar con fetch().

Así, tu app deja de usar Google Cast (que es lo que causa el overlay que
oculta el contenido) y en su lugar controla la TV como un control remoto
real.

INSTALAR:
    pip install androidtvremote2 flask flask-cors

CORRER:
    python3 backend.py
    -> queda escuchando en http://localhost:5005

ENDPOINTS:
    POST /pair/start   { "ip": "192.168.1.42" }   -> la TV muestra un código en pantalla
    POST /pair/finish  { "ip": "...", "code": "123456" } -> confirma el pairing
    POST /connect      { "ip": "192.168.1.42" }   -> conecta (usa cert ya guardado)
    POST /key          { "ip": "...", "key": "HOME" }    -> envía un botón
    GET  /status?ip=... -> estado de conexión de esa TV
"""

import asyncio
import os
import socket
import threading
import time

from flask import Flask, jsonify, request
from flask_cors import CORS
from androidtvremote2 import AndroidTVRemote, CannotConnect, InvalidAuth
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener

app = Flask(__name__)
CORS(app)  # permite que tu HTML (otro origen) le hable a este servidor

CERTS_DIR = "certs"
os.makedirs(CERTS_DIR, exist_ok=True)

# Un event loop de asyncio corriendo en un hilo aparte, porque Flask es
# síncrono pero androidtvremote2 es asíncrono.
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()


def run_coro(coro, timeout=15):
    """Ejecuta una coroutine en el event loop de fondo y espera el resultado."""
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


# ip -> instancia de AndroidTVRemote (una por TV)
remotes = {}
connected_ips = set()


def get_remote(ip: str) -> AndroidTVRemote:
    if ip not in remotes:
        safe_name = ip.replace(".", "_")
        remotes[ip] = AndroidTVRemote(
            client_name="RemoteWebApp",
            certfile=os.path.join(CERTS_DIR, f"{safe_name}.crt"),
            keyfile=os.path.join(CERTS_DIR, f"{safe_name}.key"),
            host=ip,
            loop=loop,
        )
    return remotes[ip]


@app.route("/pair/start", methods=["POST"])
def pair_start():
    data = request.get_json(force=True)
    ip = data.get("ip")
    if not ip:
        return jsonify({"error": "Falta 'ip'"}), 400

    remote = get_remote(ip)

    async def _start():
        await remote.async_generate_cert_if_missing()
        await remote.async_start_pairing()

    try:
        run_coro(_start())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "code_requested"})


@app.route("/pair/finish", methods=["POST"])
def pair_finish():
    data = request.get_json(force=True)
    ip = data.get("ip")
    code = data.get("code")
    if not ip or not code:
        return jsonify({"error": "Faltan 'ip' o 'code'"}), 400

    remote = get_remote(ip)

    async def _finish():
        await remote.async_finish_pairing(code)

    try:
        run_coro(_finish())
    except InvalidAuth:
        return jsonify({"error": "Código incorrecto"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "paired"})


@app.route("/connect", methods=["POST"])
def connect():
    data = request.get_json(force=True)
    ip = data.get("ip")
    if not ip:
        return jsonify({"error": "Falta 'ip'"}), 400

    remote = get_remote(ip)

    async def _connect():
        await remote.async_connect()
        remote.keep_reconnecting()

    try:
        run_coro(_connect())
    except CannotConnect as e:
        return jsonify({"error": f"No se pudo conectar: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    connected_ips.add(ip)
    return jsonify({"status": "connected"})


@app.route("/key", methods=["POST"])
def send_key():
    data = request.get_json(force=True)
    ip = data.get("ip")
    key = data.get("key")
    if not ip or not key:
        return jsonify({"error": "Faltan 'ip' o 'key'"}), 400
    if ip not in connected_ips:
        return jsonify({"error": "Esa TV no está conectada todavía"}), 409

    remote = get_remote(ip)
    try:
        remote.send_key_command(key)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "sent", "key": key})


ANDROID_TV_SERVICE = "_androidtvremote2._tcp.local."


class _TVListener(ServiceListener):
    def __init__(self):
        self.found = []

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if not info:
            return
        addresses = info.parsed_addresses()
        if not addresses:
            return
        friendly_name = name.replace("." + ANDROID_TV_SERVICE, "")
        self.found.append({"name": friendly_name, "ip": addresses[0]})

    def update_service(self, zc, type_, name):
        pass

    def remove_service(self, zc, type_, name):
        pass


@app.route("/discover", methods=["GET"])
def discover():
    """
    Busca Android TVs en la red local vía mDNS durante unos segundos y
    devuelve la lista de {name, ip} encontrados. No requiere saber la IP
    de antemano.
    """
    zc = Zeroconf()
    listener = _TVListener()
    browser = ServiceBrowser(zc, ANDROID_TV_SERVICE, listener)
    time.sleep(4)  # tiempo de espera para que respondan los dispositivos
    browser.cancel()
    zc.close()

    return jsonify({"devices": listener.found})


@app.route("/launch_app", methods=["POST"])
def launch_app():
    data = request.get_json(force=True)
    ip = data.get("ip")
    app_link = data.get("app_link")
    if not ip or not app_link:
        return jsonify({"error": "Faltan 'ip' o 'app_link'"}), 400
    if ip not in connected_ips:
        return jsonify({"error": "Esa TV no está conectada todavía"}), 409

    remote = get_remote(ip)
    try:
        remote.send_launch_app_command(app_link)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "launched", "app_link": app_link})


@app.route("/status", methods=["GET"])
def status():
    ip = request.args.get("ip")
    return jsonify({"ip": ip, "connected": ip in connected_ips})


if __name__ == "__main__":
    print("Servidor puente escuchando en http://localhost:5005")
    app.run(host="0.0.0.0", port=5005, debug=False)
