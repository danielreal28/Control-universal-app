# ZonaTrialApp — Control Universal Smart TV

Control remoto real para Android TV, hecho con:
- `backend.py` — servidor local en Python que habla el protocolo oficial
  "Android TV Remote v2" (el mismo que usa la app Google TV).
- `index.html` — interfaz web, adaptable a cualquier tamaño de celular.

No usa Google Cast, así que **no oculta el contenido de la TV** con overlays
de "transmitiendo" — envía pulsaciones reales de control remoto.

## Requisitos

- Python 3.10 o superior instalado (verifica con `python --version` o `py --version`).
- Que el dispositivo donde corre `backend.py` y los celulares que lo usen
  estén en la **misma red WiFi** que la Android TV.

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

1. Corre el servidor (déjalo abierto mientras uses la app):
   ```bash
   python backend.py
   ```
   Va a mostrar algo como:
   ```
   Servidor puente escuchando en http://localhost:5005
   ...
   * Running on http://<TU-IP-LOCAL>:5005
   ```
   Anota esa IP local (ej. `192.168.1.10`).

2. Abre `index.html` en el navegador de **cualquier celular conectado a esa
   misma WiFi**.

3. Toca el ícono ⚙ y en **"Servidor (backend.py)"** escribe:
   ```
   http://<TU-IP-LOCAL>:5005
   ```

4. Toca **"Buscar TV en mi red"** (o escribe la IP de la TV manualmente).

5. Toca **"Pedir código en pantalla"** → tu TV muestra un código de 6 dígitos.

6. Escribe el código → **"Confirmar código"** → **"Conectar"**.

Listo — ya puedes controlar la TV desde ese celular. Cualquier otro celular
en la misma WiFi puede repetir los pasos 2–6 (el pairing con la TV, una vez
hecho, se reutiliza automáticamente).

## Estructura del proyecto

```
ZonaTrialApp/
├── backend.py         # Servidor puente (Python) — habla con la TV real
├── index.html          # Interfaz web — se abre en cualquier navegador móvil
├── requirements.txt    # Dependencias de Python
├── LICENSE.md
└── README.md
```

## Notas

- Los certificados de vinculación (pairing) se guardan localmente en una
  carpeta `certs/` que se genera sola — no se sube a GitHub (ver `.gitignore`).
- Este proyecto controla la TV dentro de la red local. Para controlarla desde
  fuera de casa (datos móviles) se necesitaría una capa adicional (VPN o
  túnel), que no está incluida en esta versión.

---

**ZonaTrialApp** · © DanielReal 2026 · Todos los derechos reservados.
