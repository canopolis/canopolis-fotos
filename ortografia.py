# canopolis.info: corrector de tildes para nombres (espanol y otros idiomas europeos).
# 1) Lista propia de nombres y apellidos que llevan tilde.  2) Diccionarios es/pt/fr/it/de (pyspellchecker):
# si la palabra escrita sin tilde no existe y su forma con tilde si, se corrige. Nunca quita tildes puestas.
import unicodedata

NOMBRES = """Félix José Jesús María Ramón Raúl Sofía Lucía Andrés Tomás Nicolás Ángel Ángela Martín Joaquín Agustín Sebastián
Adrián Julián Fabián Germán Iván Rubén Víctor Óscar Héctor César Álvaro Gonzalo Íñigo Jerónimo Benjamín Damián Cristián
René Simón Ramiro Darío Mario Elías Matías Tobías Isaías Josué Moisés Efraín Rafael Ismael Saúl Abraham Noé Aarón Jonás
Inés Belén Raquel Mónica Verónica Angélica Érica Bárbara Débora Rocío Leonor Pilar
Eugenia Estefanía Valentín Valeria Jazmín Sinaí
García Martínez Rodríguez Hernández López González Pérez Sánchez Ramírez Gómez Díaz Jiménez Fernández Gutiérrez Álvarez
Núñez Muñoz Domínguez Vásquez Vázquez Méndez Benítez Suárez Gálvez Chávez Báez Peña Mejía Frías Grullón
Encarnación Concepción Asunción Ascensión Guzmán Durán Beltrán Calderón Rincón Colón León Marrón Monción
Almánzar Polanco Ozuna Brazobán Batista Bisonó Espaillat Ureña Peguero Solís Ríos Montás Mañón Pichardo Estévez
Velázquez Márquez Enríquez Céspedes Jáquez Báez Lugo Ogando Tejeda Germán Valerio Damirón Sosa Carrión
Avilés Hidalgo Andújar Jesús Héctor Pimentel Medina Holguín Sánchez Salomón Galván Ramón Escaño Saldaña""".split()

def sin_tilde(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")

_mapa = None
def mapa():
    global _mapa
    if _mapa is not None:
        return _mapa
    _mapa = {}
    try:
        from spellchecker import SpellChecker
        for lang in ("de", "it", "fr", "pt", "es"):          # el espanol al final: manda sobre los demas
            sc = SpellChecker(language=lang)
            freq = sc.word_frequency.dictionary
            for w, f in freq.items():
                b = sin_tilde(w)
                if "ñ" in w or "ç" in w and lang == "es":
                    continue                                  # la ñ es otra letra: no se adivina
                if lang != "es":
                    marcas = set(w) - set(b)
                    # de otros idiomas solo letras que el espanol no usa, y nunca la vocal final con acento grave (sarà, città)
                    if not marcas & set("ãõçäöüœ") or w[-1] in "àèìòù":
                        continue
                if b != w and b.isalpha() and len(b) > 2 and b not in freq:
                    if b not in _mapa or f > _mapa[b][1]:
                        _mapa[b] = (w, f)
    except Exception:
        pass
    for n in NOMBRES:                                        # la lista propia manda siempre
        _mapa[sin_tilde(n).lower()] = (n.lower(), 1.0)
    return _mapa

def corregir(texto):
    m = mapa(); out = []
    for p in texto.split():
        base = p.lower()
        if base == sin_tilde(base) and base in m:          # solo si la escribieron sin tilde
            nueva = m[base][0]
            p = nueva.upper() if p.isupper() else nueva.capitalize()
        out.append(p)
    return " ".join(out)
