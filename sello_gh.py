# canopolis.info: baja el logo con candado, arma el sello y lo devuelve con candado. No imprime datos.
import base64, hashlib, hmac, io, json, os, re, sys, time, tempfile
import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import motor_sello

SITIO = "https://www.canopolis.info/fotocola/"
job = os.environ.get("JOB", "")
llave = os.environ.get("LLAVE", "").strip()
if not re.fullmatch(r"[A-Za-z0-9\-]{10,80}", job) or not llave:
    sys.exit("datos invalidos")
clave = base64.b64decode(llave)

def firma(t):
    return hmac.new(llave.encode(), t.encode(), hashlib.sha256).hexdigest().upper()

def abrir1(iv, c):
    x = Cipher(algorithms.AES(clave), modes.CBC(iv)).decryptor()
    p = x.update(c) + x.finalize()
    u = padding.PKCS7(128).unpadder()
    return u.update(p) + u.finalize()

def abrir(d):
    try:
        return abrir1(d[:16], d[16:])
    except Exception:
        return abrir1(d[16:32], d[32:])

def cerrar(d):
    iv = os.urandom(16); pd = padding.PKCS7(128).padder(); p = pd.update(d) + pd.finalize()
    x = Cipher(algorithms.AES(clave), modes.CBC(iv)).encryptor()
    return iv + x.update(p) + x.finalize()

ts = str(int(time.time()))
r = requests.get(SITIO + "sello_logo.cfm", params={"job": job, "ts": ts, "firma": firma(f"sello|{job}|{ts}")}, timeout=60)
if r.status_code != 200 or "INICIO" not in r.text:
    sys.exit(f"no se pudo bajar el logo ({r.status_code})")
t = r.text.split("INICIO", 1)[1].rsplit("FIN", 1)[0]
t = re.sub(r"[^A-Za-z0-9+/=]", "", t).rstrip("="); t += "=" * (-len(t) % 4)
datos = json.loads(abrir(base64.b64decode(t)).decode("utf-8"))

fuente = r"C:\Windows\Fonts\verdanab.ttf"
if not os.path.exists(fuente):
    sys.exit("no esta la letra Verdana Bold")
d = tempfile.mkdtemp()
logo = os.path.join(d, "logo"); open(logo, "wb").write(base64.b64decode(datos["logo"]))
salida = os.path.join(d, "sello.png")
motor_sello.sello(logo, datos["nombre"], datos["genero"], salida, modelo="isnet.onnx", fuente=fuente)

s = base64.b64encode(cerrar(open(salida, "rb").read())).decode()
ts = str(int(time.time()))
h = hashlib.sha256(s.encode()).hexdigest().upper()
r = requests.post(SITIO + "sello_recibir.cfm", data={"job": job, "ts": ts, "sello": s, "firma": firma(f"sellorecibir|{job}|{ts}|{h}")}, timeout=120)
print("listo" if r.status_code == 200 else f"el sitio respondio {r.status_code}")
sys.exit(0 if r.status_code == 200 else 1)
