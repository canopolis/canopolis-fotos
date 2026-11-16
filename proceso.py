# canopolis.info: baja la foto con candado, le quita el fondo con BiRefNet, recorta al animal y la devuelve con candado.
# No imprime nada de la foto ni del cliente.
import base64, hashlib, hmac, io, os, re, sys, time
import numpy as np, onnxruntime as ort, requests
from PIL import Image, ImageOps
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SITIO = "https://www.canopolis.info/fotocola/"
job = os.environ.get("JOB", "")
llave = os.environ.get("LLAVE", "").strip()
if not re.fullmatch(r"[A-Za-z0-9\-]{10,80}", job) or not llave:
    sys.exit("datos invalidos")
clave = base64.b64decode(llave)

def firma(texto):
    return hmac.new(llave.encode(), texto.encode(), hashlib.sha256).hexdigest().upper()

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
    iv = os.urandom(16)
    pd = padding.PKCS7(128).padder()
    p = pd.update(d) + pd.finalize()
    x = Cipher(algorithms.AES(clave), modes.CBC(iv)).encryptor()
    return iv + x.update(p) + x.finalize()

ts = str(int(time.time()))
r = requests.get(SITIO + "foto.cfm", params={"job": job, "ts": ts, "firma": firma(f"foto|{job}|{ts}")}, timeout=60)
if r.status_code != 200:
    sys.exit(f"no se pudo bajar la foto ({r.status_code})")
t = r.text
if "INICIO" not in t or "FIN" not in t:
    sys.exit("respuesta del sitio sin marcas")
# solo lo que esta entre el primer INICIO y el ULTIMO FIN; el texto cifrado puede traer "FIN" por casualidad
payload = t.split("INICIO", 1)[1].rsplit("FIN", 1)[0]
payload = re.sub(r"[^A-Za-z0-9+/=]", "", payload)
payload = payload.rstrip("=")
payload += "=" * (-len(payload) % 4)
datos = base64.b64decode(payload)
img = ImageOps.exif_transpose(Image.open(io.BytesIO(abrir(datos)))).convert("RGB")

so = ort.SessionOptions(); so.enable_cpu_mem_arena = False; so.enable_mem_pattern = False
s = ort.InferenceSession("m.onnx", so, providers=["CPUExecutionProvider"])
x = np.asarray(img.resize((1024, 1024), Image.LANCZOS), dtype=np.float32) / 255.0
x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
x = x.transpose(2, 0, 1)[None].astype(np.float32)
m = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
m = 1 / (1 + np.exp(-m))
m = (m - m.min()) / max(m.max() - m.min(), 1e-6)
mask = Image.fromarray((m * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS)
a = np.asarray(mask)
a = np.where(a < 13, 0, a).astype(np.uint8)
out = img.convert("RGBA"); out.putalpha(Image.fromarray(a))

# recorte al animal, con un margen pequeno
ys, xs = np.where(a > 128)
if len(xs) > 50:
    w, h = img.size; mg = int(0.02 * max(w, h))
    out = out.crop((max(0, xs.min() - mg), max(0, ys.min() - mg), min(w, xs.max() + mg + 1), min(h, ys.max() + mg + 1)))
out.thumbnail((900, 900), Image.LANCZOS)
b = io.BytesIO(); out.save(b, "PNG", optimize=True)

foto = base64.b64encode(cerrar(b.getvalue())).decode()
ts = str(int(time.time()))
h = hashlib.sha256(foto.encode()).hexdigest().upper()
r = requests.post(SITIO + "recibir.cfm", data={"job": job, "ts": ts, "foto": foto, "firma": firma(f"recibir|{job}|{ts}|{h}")}, timeout=120)
print("listo" if r.status_code == 200 else f"el sitio respondio {r.status_code}")
sys.exit(0 if r.status_code == 200 else 1)
