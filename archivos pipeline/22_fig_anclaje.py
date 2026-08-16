# =============================================================================
# Caracterización de pacientes reumatológicos con GRD y ML — USACH · Diego Oliva
#
# Genera UNA figura con dos paneles (sexo y edad): este trabajo (nivel persona, eje X)
# vs Vásquez Salgado  (Figuras 2-3, eje Y), con recta identidad y enfermedades
# rotuladas SIN que los nombres se solapen (repelido de etiquetas)
# Salida: resultados_modelado_alt/figuras/anclaje.png
# USO:  python fig_anclaje.py
#   (requiere: pip install matplotlib y adjustText )
# =============================================================================
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from adjustText import adjust_text
    HAY_ADJUST = True
except Exception:
    HAY_ADJUST = False  # cae a offsets manuales si no está instalado

lab = ["AIJ", "Psoriásica", "AR", "Artrosis", "Esclerodermia", "Espondilitis",
       "Fibromialgia", "Lupus", "Miositis", "Raynaud", "Sjögren", "Uveítis"]
este_fem  = [71.5, 55.3, 77.4, 67.1, 88.7, 35.8, 96.6, 88.8, 61.4, 85.6, 93.2, 55.7]
vasq_fem  = [94,   90,   94,   92,   97,   72,   97,   95,   83,   95,   96,   89]
este_edad = [17,   54,   61,   68,   59,   49,   52,   43,   50,   49,   58,   45]
vasq_edad = [26,   45,   49,   51,   44,   40,   43,   38,   42,   41,   46,   41]

USACH = "#EA7600"


def panel(ax, x, y, titulo, unidad, rho):
    lo = min(min(x), min(y)) - 5
    hi = max(max(x), max(y)) + 5
    ax.plot([lo, hi], [lo, hi], "--", color="#b0b7c3", lw=1, zorder=1)   # recta identidad
    ax.scatter(x, y, s=38, color=USACH, edgecolor="#333F48", linewidth=0.5, zorder=3)
    if HAY_ADJUST:
        textos = [ax.text(xi, yi, li, fontsize=8, color="#333F48") for xi, yi, li in zip(x, y, lab)]
        adjust_text(textos, ax=ax, expand=(1.25, 1.5),
                    arrowprops=dict(arrowstyle="-", color="#9aa3b2", lw=0.5))
    else:  # respaldo: offset alterno arriba/abajo
        for i, (xi, yi, li) in enumerate(zip(x, y, lab)):
            dy = 7 if i % 2 == 0 else -11
            ax.annotate(li, (xi, yi), fontsize=8, color="#333F48",
                        xytext=(4, dy), textcoords="offset points")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel(f"Este trabajo ({unidad})")
    ax.set_ylabel(f"Vásquez Salgado ({unidad})")
    ax.set_title(f"{titulo}   (ρ = {rho})", fontsize=11)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, color="#eef0f2")


fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 5))
panel(a1, este_fem, vasq_fem, "Proporción de mujeres", "%", "0,93")
panel(a2, este_edad, vasq_edad, "Edad", "años", "0,96")
fig.tight_layout()
d = os.path.join(os.path.dirname(__file__), "resultados_modelado_alt", "figuras")
os.makedirs(d, exist_ok=True)
out = os.path.join(d, "anclaje.png")
fig.savefig(out, dpi=200)
print("Guardado:", out, "| repelido de etiquetas:", "sí (adjustText)" if HAY_ADJUST else "no (offset manual)")
