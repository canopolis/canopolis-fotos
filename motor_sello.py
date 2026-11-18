# canopolis.info: arma el sello de una clinica con el formato aprobado (Open Doors / ASM):
# circulo fino, nombre del profesional arriba, titulo segun genero abajo, logo grande al centro,
# un solo azul CEMVET (66,125,237), fondo transparente, letras Verdana Bold.
import math, sys, unicodedata
import numpy as np, onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

AZUL = (66, 125, 237)
N = 1500                     # tamano final del sello
C = N / 2
R_ARO = 735                  # radio del circulo fino
G_ARO = 9                    # grueso del circulo
R_TXT = 648                  # radio del centro de las letras
ALTO_TXT = 74                # alto de las mayusculas
R_LOGO = 570                 # lo mas lejos que llega el logo (justo por dentro de las letras)
ESPACIO = 0.30               # separacion entre letras (fraccion del alto)
LIMITE = 158                 # angulo maximo que ocupa un texto

def titulo(genero):
    return "MÉDICA VETERINARIA" if genero.upper().startswith("F") else "MÉDICO VETERINARIO"

def mayus(t):
    return unicodedata.normalize("NFC", t.strip().upper())

def quitar_fondo(img, modelo):
    s = ort.InferenceSession(modelo, providers=["CPUExecutionProvider"])
    x = np.asarray(img.convert("RGB").resize((1024, 1024), Image.LANCZOS), dtype=np.float32) / 255.0
    x = (x - 0.5) / 1.0
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    m = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
    m = (m - m.min()) / max(m.max() - m.min(), 1e-6)
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS)) / 255.0

def logo_azul(ruta, modelo):
    img = ImageOps.exif_transpose(Image.open(ruta))
    if max(img.size) < 1200:                     # 2026-11-18: logos chicos se agrandan antes de limpiar (bordes suaves, rayas finas no se pierden)
        k = 1200.0 / max(img.size)
        img = img.convert("RGBA").resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    rgba = img.convert("RGBA")
    a0 = np.asarray(rgba)[:, :, 3] / 255.0
    rgb = np.asarray(rgba.convert("RGB")).astype(float)
    # fuerza de tinta = cuanto se aleja del blanco el canal mas oscuro (negro, colores fuertes y claros cuentan;
    # blanco, grises claros, sombras, halos y ruido del JPG no)
    fuerza = 255 - rgb.min(axis=2)
    tinta = np.clip((fuerza - 70) / 45.0, 0, 1)
    h, w = fuerza.shape
    borde = np.concatenate([fuerza[0], fuerza[-1], fuerza[:, 0], fuerza[:, -1]])
    rb = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    cb = np.median(rb, axis=0)
    parejo = np.abs(rb - cb).max(axis=1).mean() < 25     # borde de un solo color
    if a0.min() < 0.99:                          # ya trae transparencia: se respeta
        a = tinta * a0
    elif (borde < 70).mean() > 0.6:              # fondo claro (blanco o gris de captura): basta con la tinta
        a = tinta
    elif parejo:                                 # 2026-11-18: logo dentro de un marco de un solo color (ej. Clinica America):
        from scipy import ndimage                # se quita solo ese color conectado al borde de la imagen; lo de adentro se queda
        lab0, n0 = ndimage.label(np.abs(rgb - cb).max(axis=2) < 40)
        toca0 = set(np.unique(np.concatenate([lab0[0], lab0[-1], lab0[:, 0], lab0[:, -1]]))) - {0}
        fuera = ndimage.binary_dilation(np.isin(lab0, list(toca0)), iterations=max(2, int(round(min(h, w) / 100))))
        a = np.clip((fuerza - 30) / 45.0, 0, 1) * (~fuera)   # el fondo ya se quito por forma: las rayas finas claras se conservan
    else:                                        # foto sobre fondo oscuro o de color: motor de quitar fondo
        fondo = (quitar_fondo(img, modelo) > 0.5).astype(np.uint8) * 255
        fondo = np.asarray(Image.fromarray(fondo).filter(ImageFilter.GaussianBlur(1))) / 255.0
        a = tinta * fondo
    # 2026-11-18: si el logo tiene tinta oscura (letras) y tinta clara (dibujos), lo claro queda en azul mas suave
    # para que las letras se distingan cuando van encima del dibujo
    hay = a > 0.3
    if hay.sum() > 0:
        oscuro = (fuerza > 200) & hay
        claro = (fuerza < 170) & hay
        if oscuro.sum() > 0.05 * hay.sum() and claro.sum() > 0.05 * hay.sum():
            a = a * np.clip((fuerza - 40) / 160.0, 0.6, 1)
    a = np.where(a < 0.08, 0, a)
    from scipy import ndimage
    lab, n = ndimage.label(a > 0.3)
    if n:
        idx = np.arange(1, n + 1)
        tam = ndimage.sum(np.ones_like(a), lab, idx)
        # fuera: pedazos que tocan el borde de la imagen (restos de fondo) y puntitos sueltos
        toca = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        malos = [i for i, t in zip(idx, tam) if i in toca or t < max(30, 0.0005 * tam.sum())]
        if len(malos) < n:
            buenos = np.isin(lab, [i for i in idx if i not in malos])
            cerca = ndimage.binary_dilation(buenos, iterations=2)
            a = np.where(cerca, a, 0)
    m = Image.fromarray((a * 255).astype(np.uint8))
    out = Image.new("RGBA", img.size, AZUL + (0,))
    out.putalpha(m)
    bb = m.point(lambda v: 255 if v > 20 else 0).getbbox()
    return out.crop(bb) if bb else out

def letra(ch, fuente):
    l, t, r, b = fuente.getbbox(ch)
    w = max(int(fuente.getlength(ch)), 1)
    im = Image.new("L", (w + 40, int(ALTO_TXT * 2.2)), 0)
    ImageDraw.Draw(im).text((20, int(ALTO_TXT * 0.6)), ch, font=fuente, fill=255)
    return im, w

def texto_en_arco(lienzo, texto, fuente, arriba):
    # ancho total en angulo
    tam = []
    for ch in texto:
        if ch == " ":
            tam.append((None, fuente.getlength(" ") * 1.1))
        else:
            im, w = letra(ch, fuente)
            tam.append((im, w))
    paso = ALTO_TXT * ESPACIO
    total = sum(w for _, w in tam) + paso * (len(tam) - 1)
    ang_total = total / R_TXT
    if ang_total > math.radians(LIMITE):
        raise ValueError("largo")
    th = (-math.pi / 2 - ang_total / 2) if arriba else (math.pi / 2 + ang_total / 2)
    capa = Image.new("L", (N, N), 0)
    # centro vertical de las mayusculas dentro de la imagen de cada letra
    cap = fuente.getbbox("H")
    cy_letra = int(ALTO_TXT * 0.6) + (cap[1] + cap[3]) / 2
    for im, w in tam:
        da = (w / 2) / R_TXT
        th += da if arriba else -da
        if im is not None:
            W = max(im.size) * 2
            cv = Image.new("L", (W, W), 0)
            cv.paste(im, (int(W / 2 - im.width / 2), int(W / 2 - cy_letra)))
            giro = -(math.degrees(th) + 90) if arriba else -(math.degrees(th) - 90)
            rot = cv.rotate(giro, resample=Image.BICUBIC)
            x, y = C + R_TXT * math.cos(th), C + R_TXT * math.sin(th)
            capa.paste(rot, (int(round(x - W / 2)), int(round(y - W / 2))), rot)
        th += (da + paso / R_TXT) if arriba else -(da + paso / R_TXT)
    lienzo.paste(Image.new("RGBA", (N, N), AZUL + (255,)), (0, 0), capa)

def sello(logo, nombre, genero, salida, modelo="isnet.onnx", fuente="verdanab.ttf"):
    import ortografia
    nombre = ortografia.corregir(" ".join(nombre.split()))
    f = ImageFont.truetype(fuente, 10)
    cap = f.getbbox("H"); f = ImageFont.truetype(fuente, int(10 * ALTO_TXT / (cap[3] - cap[1])))
    s = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    # circulo fino (dibujado en grande para que quede suave)
    k = 4; aro = Image.new("L", (N * k, N * k), 0)
    ImageDraw.Draw(aro).ellipse([(C - R_ARO) * k, (C - R_ARO) * k, (C + R_ARO) * k, (C + R_ARO) * k], outline=255, width=G_ARO * k)
    s.paste(Image.new("RGBA", (N, N), AZUL + (255,)), (0, 0), aro.resize((N, N), Image.LANCZOS))
    tam = 10 * ALTO_TXT / (cap[3] - cap[1])
    while True:        # mismo tamano arriba y abajo; se achica solo si alguno no cabe
        prueba = s.copy()
        try:
            for t, arriba in ((mayus(nombre), True), (titulo(genero), False)):
                texto_en_arco(prueba, t, ImageFont.truetype(fuente, int(tam)), arriba)
            s = prueba; break
        except ValueError:
            tam *= 0.96
    lg = logo_azul(logo, modelo)
    w, h = lg.size
    # el logo se agranda hasta que su punto mas lejano (no la esquina de la caja) toca el borde interior de las letras
    al = np.asarray(lg)[:, :, 3]
    ys, xs = np.nonzero(al > 20)
    rmax = max(np.hypot(xs - w / 2, ys - h / 2).max(), 1) if len(xs) else math.hypot(w / 2, h / 2)
    esc = R_LOGO / rmax
    lg = lg.resize((max(1, int(w * esc)), max(1, int(h * esc))), Image.LANCZOS)
    s.alpha_composite(lg, (int(C - lg.width / 2), int(C - lg.height / 2)))
    # un solo azul puro: solo cambia la transparencia
    a = s.split()[3]
    fin = Image.new("RGBA", (N, N), AZUL + (0,)); fin.putalpha(a)
    fin.save(salida, optimize=True)
    return nombre

if False:
    sello(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
