"""Visualizaciones y series de rendimiento independientes de la interfaz."""

from collections import defaultdict
from html import escape

import plotly.graph_objects as go


PALETA = ["#8de5c2", "#92bafa", "#e7c88c", "#ccabef", "#f29e8e", "#85d6e0", "#e4a5cb", "#c2d68c"]
METRICAS = {
    "Efectividad": ("porcentaje", "% de victorias", "%"),
    "Victorias": ("victorias", "Victorias acumuladas", ""),
    "Balance": ("balance", "Diferencia de puntos", " pts"),
}
CONFIG_GRAFICO = {"displayModeBar": False, "scrollZoom": False, "responsive": True}


def colores_jugadores(nombres):
    """El color no cambia al seleccionar o quitar jugadores."""
    return {nombre: PALETA[i % len(PALETA)] for i, nombre in enumerate(sorted(nombres))}


def tema_grafico(fig, altura=380):
    fig.update_layout(
        template="plotly_dark",
        colorway=PALETA,
        paper_bgcolor="#151f22", plot_bgcolor="#151f22",
        font=dict(family="Segoe UI, sans-serif", color="#a3b4b7", size=12),
        margin=dict(l=24, r=30, t=30, b=24),
        height=altura,
        hovermode="closest",
        hoverlabel=dict(bgcolor="#22372f", bordercolor="#49695c", font_color="#edf3f0"),
        legend=dict(title_text="", orientation="h", y=-.18, x=0, font_size=12),
        modebar=dict(remove=["lasso2d", "select2d"]),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, automargin=True, title_font_size=11)
    fig.update_yaxes(gridcolor="#29373b", griddash="dot", zeroline=False, automargin=True, title_font_size=11)
    return fig


def series_rendimiento(partidas, nombres):
    """Acumula desde el inicio del periodo; conserva partidas en la misma fecha."""
    series = {nombre: [] for nombre in nombres}
    acumulados = defaultdict(lambda: {"pj": 0, "pg": 0, "balance": 0})
    for partida in sorted(partidas, key=lambda p: p["fecha"]):
        if partida["empate"]:
            continue
        for equipo, rival in ((1, 2), (2, 1)):
            for nombre in partida[f"jugadores{equipo}"]:
                if nombre not in series:
                    continue
                dato = acumulados[nombre]
                dato["pj"] += 1
                dato["pg"] += int(partida["ganador"] == f"equipo{equipo}")
                dato["balance"] += partida[f"puntos{equipo}"] - partida[f"puntos{rival}"]
                series[nombre].append({
                    "fecha": partida["fecha"], "partida": dato["pj"],
                    "victorias": dato["pg"], "derrotas": dato["pj"] - dato["pg"],
                    "porcentaje": 100 * dato["pg"] / dato["pj"], "balance": dato["balance"],
                })
    return series


def grafico_evolucion(series, metrica, eje, colores):
    campo, titulo, sufijo = METRICAS[metrica]
    por_fecha = eje == "Fecha"
    fig = go.Figure()
    for indice, (nombre, puntos) in enumerate(series.items()):
        if not puntos:
            continue
        color = colores[nombre]
        fig.add_trace(go.Scatter(
            x=[p["fecha"] if por_fecha else p["partida"] for p in puntos],
            y=[p[campo] for p in puntos],
            name=escape(nombre), mode="lines+markers", connectgaps=False,
            line=dict(color=color, width=3, dash=["solid", "dash", "dot", "dashdot"][indice % 4]),
            marker=dict(size=8, color=color, line=dict(color="#151f22", width=2)),
            customdata=[[p["fecha"].strftime("%d/%m/%Y"), p["partida"], p["victorias"]] for p in puntos],
            hovertemplate=(
                "<b>%{fullData.name}</b><br>%{customdata[0]} · Partida %{customdata[1]}"
                f"<br><b>%{{y:.1f}}{sufijo}</b>"
                "<br>%{customdata[2]} victorias<extra></extra>"
            ),
        ))
    tema_grafico(fig, 430)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title_text=titulo)
    if metrica == "Efectividad":
        fig.update_yaxes(range=[-5, 105], ticksuffix="%", dtick=25)
        fig.add_hline(y=50, line_dash="dot", line_color="#607568", line_width=1, layer="below")
    elif metrica == "Victorias":
        fig.update_yaxes(rangemode="tozero", dtick=1, tickformat="d")
    else:
        fig.add_hline(y=0, line_color="#7c9388", line_width=1, layer="below")
    if por_fecha:
        fig.update_xaxes(type="date", tickformat="%d/%m/%Y", nticks=7)
    else:
        fig.update_xaxes(title_text="Partidas jugadas por cada jugador", dtick=1, tickformat="d")
    return fig


def grafico_balance(series, colores):
    datos = sorted(
        [(nombre, puntos[-1]) for nombre, puntos in series.items() if puntos],
        key=lambda item: (-item[1]["victorias"], item[0]),
    )
    nombres = [escape(nombre) for nombre, _ in datos]
    fig = go.Figure()
    for campo, etiqueta, signo, color in [
        ("derrotas", "Derrotas", -1, "#d18d89"),
        ("victorias", "Victorias", 1, "#8de5c2"),
    ]:
        valores = [dato[campo] for _, dato in datos]
        fig.add_trace(go.Bar(
            y=nombres, x=[signo * v for v in valores], orientation="h", name=etiqueta,
            marker_color=color, customdata=valores,
            text=[str(v) if v else "" for v in valores], textposition="inside",
            textfont=dict(color="#101b18"),
            hovertemplate=f"%{{y}}<br>%{{customdata}} {etiqueta.lower()}<extra></extra>",
        ))
    tema_grafico(fig, max(310, len(datos) * 46 + 100))
    limite = max([max(d["victorias"], d["derrotas"]) for _, d in datos], default=1) or 1
    fig.update_layout(barmode="relative", bargap=.48)
    fig.update_xaxes(range=[-limite - .6, limite + .6], tickvals=[-limite, 0, limite], ticktext=[str(limite), "0", str(limite)])
    fig.update_yaxes(showgrid=False, categoryorder="array", categoryarray=nombres, autorange="reversed")
    fig.add_vline(x=0, line_color="#52655e", line_width=1)
    return fig


def grafico_parejas(parejas):
    principales = sorted(parejas, key=lambda p: (-p["pct_victorias"], -p["pj"], p["pareja"]))[:6]
    nombres = [escape(p["pareja"]) for p in principales]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[100] * len(nombres), y=nombres, orientation="h", marker_color="#243236",
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Bar(
        x=[p["pct_victorias"] for p in principales], y=nombres, orientation="h",
        marker_color="#e7c88c", showlegend=False,
        text=[f'{p["pct_victorias"]:.0f}%' for p in principales], textposition="outside",
        textfont_color="#edf3f0", cliponaxis=False,
        customdata=[[p["pg"], p["pj"]] for p in principales],
        hovertemplate="%{y}<br><b>%{x:.1f}% de victorias</b><br>%{customdata[0]} ganadas de %{customdata[1]} jugadas<extra></extra>",
    ))
    tema_grafico(fig, max(310, len(nombres) * 46 + 100))
    fig.update_layout(barmode="overlay", bargap=.6)
    fig.update_xaxes(range=[0, 120], tickvals=[0, 50, 100], ticksuffix="%")
    fig.update_yaxes(showgrid=False, categoryorder="array", categoryarray=nombres, autorange="reversed")
    return fig