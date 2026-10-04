# -*- coding: utf-8 -*-
"""
MusStats ♠️ — Dashboard de estadísticas de partidas de Mus
Ejecutar con: streamlit run app.py
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from charts import (
    CONFIG_GRAFICO, METRICAS, colores_jugadores, grafico_balance,
    grafico_evolucion, grafico_parejas, series_rendimiento, tema_grafico,
)


# ===========================================================================
# CONFIGURACIÓN DE LA PÁGINA
# ===========================================================================

st.set_page_config(
    page_title="MusStats ♠️",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===========================================================================
# ESTILOS
# ===========================================================================

def inyectar_css():
    css = (Path(__file__).resolve().parent / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ===========================================================================
# CARGA Y PROCESADO DE DATOS
# ===========================================================================

def cargar_datos():
    """Lee las partidas del JSON situado junto a esta aplicación."""
    ruta = Path(__file__).resolve().parent / "partidas.json"

    try:
        with ruta.open(encoding="utf-8") as archivo:
            partidas = json.load(archivo)
    except (OSError, json.JSONDecodeError) as error:
        st.error(f"No se pudo cargar {ruta.name}: {error}")
        st.stop()

    if not isinstance(partidas, list):
        st.error(f"{ruta.name} debe contener una lista de partidas.")
        st.stop()

    return partidas


def _parsear_fecha(fecha_str):
    """Convierte DD/MM/AAAA en datetime."""
    if not fecha_str or not isinstance(fecha_str, str):
        return None

    try:
        return datetime.strptime(fecha_str.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def _pareja_key(j1, j2):
    """Clave canónica de una pareja: el orden no importa."""
    return tuple(sorted([j1, j2]))


def pareja_nombre(j1, j2):
    """Nombre legible de una pareja."""
    return f"{j1} + {j2}"


def formatear_fecha(fecha):
    """Devuelve una fecha siempre en formato DD/MM/AAAA."""
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y")


def procesar_partidas(partidas_raw):
    """
    Normaliza y valida las partidas en bruto.
    Descarta partidas incompletas o con fechas incorrectas.
    Conserva los empates pero no los utiliza para estadísticas.
    """
    procesadas = []

    for p in partidas_raw:
        try:
            eq1 = p.get("equipo1", {}) or {}
            eq2 = p.get("equipo2", {}) or {}

            j1a, j1b = eq1.get("jugador1"), eq1.get("jugador2")
            j2a, j2b = eq2.get("jugador1"), eq2.get("jugador2")

            pts1, pts2 = eq1.get("puntos"), eq2.get("puntos")
            fecha = _parsear_fecha(p.get("fecha"))

            if not all([j1a, j1b, j2a, j2b]):
                continue

            if pts1 is None or pts2 is None or fecha is None:
                continue

            if not isinstance(pts1, (int, float)) or not isinstance(pts2, (int, float)):
                continue

            empate = pts1 == pts2

            ganador = None
            if not empate:
                ganador = "equipo1" if pts1 > pts2 else "equipo2"

            procesadas.append(
                {
                    "fecha": fecha,
                    "fecha_str": formatear_fecha(fecha),
                    "jugadores1": (j1a, j1b),
                    "jugadores2": (j2a, j2b),
                    "pareja1": _pareja_key(j1a, j1b),
                    "pareja2": _pareja_key(j2a, j2b),
                    "puntos1": pts1,
                    "puntos2": pts2,
                    "empate": empate,
                    "ganador": ganador,
                }
            )

        except Exception:
            continue

    procesadas.sort(key=lambda x: x["fecha"])
    return procesadas


# ===========================================================================
# RACHAS
# ===========================================================================

def calcular_rachas(resultados_cronologicos):
    """
    Devuelve:
    - racha actual
    - mejor racha de victorias
    - peor racha de derrotas
    """
    if not resultados_cronologicos:
        return "—", 0, 0

    mejor_racha_v = 0
    peor_racha_d = 0

    racha_v = 0
    racha_d = 0

    for resultado in resultados_cronologicos:
        if resultado == "V":
            racha_v += 1
            racha_d = 0
            mejor_racha_v = max(mejor_racha_v, racha_v)
        else:
            racha_d += 1
            racha_v = 0
            peor_racha_d = max(peor_racha_d, racha_d)

    ultimo = resultados_cronologicos[-1]

    contador = 0
    for resultado in reversed(resultados_cronologicos):
        if resultado == ultimo:
            contador += 1
        else:
            break

    racha_actual = (
        f"🔥 {contador}V"
        if ultimo == "V"
        else f"❌ {contador}D"
    )

    return racha_actual, mejor_racha_v, peor_racha_d


# ===========================================================================
# ESTADÍSTICAS DE JUGADORES
# ===========================================================================

def calcular_estadisticas_jugadores(partidas_procesadas):
    """Calcula estadísticas individuales por jugador."""
    validas = [p for p in partidas_procesadas if not p["empate"]]

    jugadores = set()

    for p in validas:
        jugadores.update(p["jugadores1"])
        jugadores.update(p["jugadores2"])

    stats = {}

    for jugador in sorted(jugadores):
        resultados = []

        pj = 0
        pg = 0
        pp = 0
        pf = 0
        pc = 0

        for p in validas:
            if jugador in p["jugadores1"]:
                propios = p["puntos1"]
                rival = p["puntos2"]
                gano = p["ganador"] == "equipo1"

            elif jugador in p["jugadores2"]:
                propios = p["puntos2"]
                rival = p["puntos1"]
                gano = p["ganador"] == "equipo2"

            else:
                continue

            pj += 1
            pf += propios
            pc += rival

            if gano:
                pg += 1
                resultados.append("V")
            else:
                pp += 1
                resultados.append("D")

        pct_v = (pg / pj * 100) if pj > 0 else 0.0
        pct_d = (pp / pj * 100) if pj > 0 else 0.0

        racha_actual, mejor_racha, peor_racha = calcular_rachas(resultados)

        stats[jugador] = {
            "jugador": jugador,
            "pj": pj,
            "pg": pg,
            "pp": pp,
            "pct_victorias": round(pct_v, 1),
            "pct_derrotas": round(pct_d, 1),
            "puntos_favor": pf,
            "puntos_contra": pc,
            "diferencia": pf - pc,
            "racha_actual": racha_actual,
            "mejor_racha_victorias": mejor_racha,
            "peor_racha_derrotas": peor_racha,
        }

    return stats


# ===========================================================================
# ESTADÍSTICAS DE PAREJAS
# ===========================================================================

def calcular_estadisticas_parejas(partidas_procesadas):
    """Calcula estadísticas por pareja."""
    validas = [p for p in partidas_procesadas if not p["empate"]]

    parejas = set()

    for p in validas:
        parejas.add(p["pareja1"])
        parejas.add(p["pareja2"])

    stats = {}

    for pareja in sorted(parejas):
        resultados = []

        pj = 0
        pg = 0
        pp = 0
        pf = 0
        pc = 0

        for p in validas:
            if p["pareja1"] == pareja:
                propios = p["puntos1"]
                rival = p["puntos2"]
                gano = p["ganador"] == "equipo1"

            elif p["pareja2"] == pareja:
                propios = p["puntos2"]
                rival = p["puntos1"]
                gano = p["ganador"] == "equipo2"

            else:
                continue

            pj += 1
            pf += propios
            pc += rival

            if gano:
                pg += 1
                resultados.append("V")
            else:
                pp += 1
                resultados.append("D")

        pct_v = (pg / pj * 100) if pj > 0 else 0.0
        pct_d = (pp / pj * 100) if pj > 0 else 0.0

        racha_actual, mejor_racha, peor_racha = calcular_rachas(resultados)

        stats[pareja] = {
            "pareja": pareja_nombre(*pareja),
            "jugadores": pareja,
            "pj": pj,
            "pg": pg,
            "pp": pp,
            "pct_victorias": round(pct_v, 1),
            "pct_derrotas": round(pct_d, 1),
            "puntos_favor": pf,
            "puntos_contra": pc,
            "diferencia": pf - pc,
            "racha_actual": racha_actual,
            "mejor_racha_victorias": mejor_racha,
            "peor_racha_derrotas": peor_racha,
        }

    return stats


# ===========================================================================
# COMPAÑEROS
# ===========================================================================

def calcular_companeros(partidas_procesadas):
    """Calcula la relación entre compañeros."""
    validas = [p for p in partidas_procesadas if not p["empate"]]

    datos = defaultdict(
        lambda: defaultdict(
            lambda: {"pj": 0, "pg": 0, "pp": 0}
        )
    )

    for p in validas:
        equipos = (
            (p["jugadores1"], p["ganador"] == "equipo1"),
            (p["jugadores2"], p["ganador"] == "equipo2"),
        )

        for (j1, j2), gano in equipos:
            for jugador, companero in ((j1, j2), (j2, j1)):
                d = datos[jugador][companero]

                d["pj"] += 1

                if gano:
                    d["pg"] += 1
                else:
                    d["pp"] += 1

    resultado = {}

    for jugador, companeros in datos.items():
        lista = []

        for companero, d in companeros.items():
            pct_v = (
                d["pg"] / d["pj"] * 100
                if d["pj"] > 0
                else 0.0
            )

            pct_d = (
                d["pp"] / d["pj"] * 100
                if d["pj"] > 0
                else 0.0
            )

            lista.append(
                {
                    "companero": companero,
                    "pj": d["pj"],
                    "pg": d["pg"],
                    "pp": d["pp"],
                    "pct_victorias": round(pct_v, 1),
                    "pct_derrotas": round(pct_d, 1),
                }
            )

        if not lista:
            resultado[jugador] = None
            continue

        mas_victorias = max(
            lista,
            key=lambda x: (x["pg"], x["pct_victorias"])
        )

        mayor_pct_victorias = max(
            lista,
            key=lambda x: (x["pct_victorias"], x["pj"])
        )

        mas_derrotas = max(
            lista,
            key=lambda x: (x["pp"], x["pct_derrotas"])
        )

        resultado[jugador] = {
            "mas_victorias": mas_victorias,
            "mayor_pct_victorias": mayor_pct_victorias,
            "mas_derrotas": mas_derrotas,
        }

    return resultado


# ===========================================================================
# RANKING
# ===========================================================================

def crear_ranking(stats_jugadores, criterio="pct_victorias"):
    """Crea ranking de jugadores."""

    lista = list(stats_jugadores.values())

    if criterio == "victorias":
        lista.sort(
            key=lambda x: (
                -x["pg"],
                -x["pct_victorias"],
                x["jugador"],
            )
        )

    elif criterio == "diferencia":
        lista.sort(
            key=lambda x: (
                -x["diferencia"],
                x["jugador"],
            )
        )

    elif criterio == "nombre":
        lista.sort(
            key=lambda x: x["jugador"]
        )

    else:
        lista.sort(
            key=lambda x: (
                -x["pct_victorias"],
                -x["pg"],
                -x["diferencia"],
                x["jugador"],
            )
        )

    for i, item in enumerate(lista, start=1):
        item["posicion"] = i

    return lista


# ===========================================================================
# FILTROS
# ===========================================================================

def aplicar_filtros(
    partidas_procesadas,
    jugadores=None,
    parejas=None,
    fecha_desde=None,
    fecha_hasta=None,
    incluir_empates=False,
):
    """Aplica los filtros globales sobre las partidas."""

    filtradas = []

    for p in partidas_procesadas:

        if not incluir_empates and p["empate"]:
            continue

        if jugadores is not None:
            jugadores_partida = set(
                p["jugadores1"] + p["jugadores2"]
            )

            if not jugadores_partida.intersection(jugadores):
                continue

        if parejas is not None:
            if (
                p["pareja1"] not in parejas
                and p["pareja2"] not in parejas
            ):
                continue

        if fecha_desde and p["fecha"] < fecha_desde:
            continue

        if fecha_hasta and p["fecha"] > fecha_hasta:
            continue

        filtradas.append(p)

    return filtradas


# ===========================================================================
# COMPONENTES VISUALES
# ===========================================================================

def reiniciar_filtros_partidas():
    for clave in ("part_jugadores", "part_parejas"):
        st.session_state[clave] = []
    st.session_state["part_busqueda"] = ""
    st.session_state["part_periodo"] = "Todo el histórico"
    st.session_state.pop("part_rango", None)


def seleccionar_jugadores_evolucion(nombres):
    st.session_state["evolucion_jugadores"] = nombres


def control_periodo(prefijo, partidas):
    """Periodos relativos a la última partida, no a la fecha del dispositivo."""
    inicio = min(p["fecha"] for p in partidas).date()
    fin = max(p["fecha"] for p in partidas).date()
    periodo = st.selectbox(
        "Periodo", ["Todo el histórico", "Últimos 30 días", "Últimos 90 días", "Personalizado"],
        key=f"{prefijo}_periodo", label_visibility="collapsed",
    )
    if periodo == "Personalizado":
        rango = st.date_input(
            "Rango de fechas", value=(inicio, fin), min_value=inicio, max_value=fin,
            format="DD/MM/YYYY", key=f"{prefijo}_rango",
        )
        if len(rango) != 2:
            st.caption("Selecciona la fecha final para completar el periodo.")
            return None
        inicio, fin = rango
    elif periodo != "Todo el histórico":
        dias = 30 if periodo == "Últimos 30 días" else 90
        inicio = max(inicio, fin - timedelta(days=dias - 1))
    return datetime.combine(inicio, datetime.min.time()), datetime.combine(fin, datetime.max.time())


def tarjeta_stat(col, icono, valor, etiqueta):
    with col:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="icono" aria-hidden="true">{escape(str(icono))}</div>
                <div class="etiqueta">{escape(str(etiqueta))}</div>
                <div class="valor">{escape(str(valor))}</div>
                <div class="stat-note">Histórico de la cuadrilla</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def mensaje_vacio(
    texto="No hay resultados para los filtros seleccionados."
):
    st.markdown(
        f'<div class="mensaje-vacio">{escape(texto)}</div>',
        unsafe_allow_html=True,
    )


def titulo_seccion(titulo, detalle=""):
    st.markdown(
        f'<div class="section-heading"><h3>{escape(titulo)}</h3>'
        f'<span>{escape(detalle)}</span></div>',
        unsafe_allow_html=True,
    )


def estilizar_grafico(fig):
    """Aplica la misma paleta y jerarquía a todas las visualizaciones."""
    return tema_grafico(fig)


def mostrar_pulso(partidas, stats_jugadores):
    """Combina clasificación y actividad reciente sin alterar los cálculos."""
    ranking_col, actividad_col = st.columns([1.1, 1], gap="large")
    with ranking_col:
        titulo_seccion("Así está la mesa", "TOP 6 · % de victorias")
        lideres = crear_ranking(stats_jugadores)[:6]
        fig = go.Figure(go.Bar(
            x=[s["pct_victorias"] for s in lideres],
            y=[escape(s["jugador"]) for s in lideres],
            orientation="h",
            marker=dict(color=["#8de5c2"] + ["#497f69"] * (len(lideres) - 1)),
            text=[f'{s["pct_victorias"]:.1f}%' for s in lideres],
            textposition="outside",
            textfont=dict(color="#edf3f0", size=12),
            cliponaxis=False,
            customdata=[[s["pg"], s["pj"]] for s in lideres],
            hovertemplate="%{y}<br>%{x:.1f}% de victorias<br>%{customdata[0]} ganadas / %{customdata[1]} jugadas<extra></extra>",
        ))
        estilizar_grafico(fig)
        fig.update_layout(height=340, bargap=.48, hovermode="closest", showlegend=False)
        fig.update_xaxes(range=[0, 118], ticksuffix="%", tickvals=[0, 25, 50, 75, 100])
        fig.update_yaxes(
            autorange="reversed", showgrid=False, tickfont_color="#edf3f0",
            categoryorder="array", categoryarray=[escape(s["jugador"]) for s in lideres],
        )
        st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})
        st.caption("Ordenado por porcentaje de victorias; sin mínimo de partidas.")

    with actividad_col:
        titulo_seccion("Últimas partidas", "ACTIVIDAD RECIENTE")
        filas = []
        for p in sorted(partidas, key=lambda p: p["fecha"], reverse=True)[:4]:
            clase1 = "winner" if p["ganador"] == "equipo1" else ""
            clase2 = "winner" if p["ganador"] == "equipo2" else ""
            filas.append(
                f'<div class="match-row"><div class="match-date">{escape(p["fecha_str"])}</div>'
                f'<div class="match-teams"><span class="{clase1}">{escape(pareja_nombre(*p["jugadores1"]))}</span>'
                f'<strong class="score">{p["puntos1"]} : {p["puntos2"]}</strong>'
                f'<span class="{clase2}">{escape(pareja_nombre(*p["jugadores2"]))}</span></div></div>'
            )
        st.markdown('<div class="activity-panel">' + "".join(filas) + '</div>', unsafe_allow_html=True)
        st.caption("La pareja ganadora aparece en verde · Marcador final.")


# ===========================================================================
# TABLA JUGADORES
# ===========================================================================

def tabla_jugadores_df(lista_stats):
    filas = []

    for i, s in enumerate(
        sorted(
            lista_stats,
            key=lambda x: (
                -x["pct_victorias"],
                -x["pg"],
                x["jugador"],
            ),
        ),
        start=1,
    ):
        filas.append(
            {
                "Posición": i,
                "Jugador": s["jugador"],
                "PJ": s["pj"],
                "PG": s["pg"],
                "PP": s["pp"],
                "% Victorias": f'{s["pct_victorias"]:.1f}%',
                "% Derrotas": f'{s["pct_derrotas"]:.1f}%',
                "Dif. Puntos": s["diferencia"],
                "Racha": s["racha_actual"],
            }
        )

    return pd.DataFrame(filas)


# ===========================================================================
# TABLA PAREJAS
# ===========================================================================

def tabla_parejas_df(lista_stats):
    filas = []

    for i, s in enumerate(
        sorted(
            lista_stats,
            key=lambda x: (
                -x["pct_victorias"],
                -x["pg"],
                x["pareja"],
            ),
        ),
        start=1,
    ):
        filas.append(
            {
                "Posición": i,
                "Pareja": s["pareja"],
                "PJ": s["pj"],
                "PG": s["pg"],
                "PP": s["pp"],
                "% Victorias": f'{s["pct_victorias"]:.1f}%',
                "% Derrotas": f'{s["pct_derrotas"]:.1f}%',
                "Dif. Puntos": s["diferencia"],
                "Racha": s["racha_actual"],
                "Mejor racha V": s["mejor_racha_victorias"],
            }
        )

    return pd.DataFrame(filas)


# ===========================================================================
# VISTA: DASHBOARD
# ===========================================================================

def mostrar_dashboard(
    partidas_procesadas,
    stats_jugadores,
    stats_parejas,
):
    validas = [
        p for p in partidas_procesadas
        if not p["empate"]
    ]

    empates = [
        p for p in partidas_procesadas
        if p["empate"]
    ]

    n_jugadores = len(stats_jugadores)
    n_parejas = len(stats_parejas)

    titulo_seccion("La partida, en cifras", "UNA MIRADA AL HISTÓRICO")

    # Quitado KPI de victorias totales
    c1, c2, c3, c4 = st.columns(4)

    tarjeta_stat(
        c1,
        "♠",
        len(validas),
        "Partidas válidas",
    )

    tarjeta_stat(
        c2,
        "=",
        len(empates),
        "Empates descartados",
    )

    tarjeta_stat(
        c3,
        "♙",
        n_jugadores,
        "Jugadores",
    )

    tarjeta_stat(
        c4,
        "♧",
        n_parejas,
        "Parejas",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if not stats_jugadores:
        mensaje_vacio(
            "Todavía no hay partidas válidas registradas."
        )
        return

    # -----------------------------------------------------------------------
    # Lo más destacado
    # -----------------------------------------------------------------------

    mostrar_pulso(validas, stats_jugadores)
    titulo_seccion("Nombres propios", "LOS MÁS DESTACADOS")

    col1, col2, col3 = st.columns(3)

    # En empate de porcentaje, gana quien haya jugado más partidas
    mejor_pct = max(
        stats_jugadores.values(),
        key=lambda x: (
            x["pct_victorias"],
            x["pj"],
            x["pg"],
            x["jugador"],
        ),
    )

    mas_victorias = max(
        stats_jugadores.values(),
        key=lambda x: (
            x["pg"],
            x["pct_victorias"],
            x["jugador"],
        ),
    )

    mejor_dif = max(
        stats_jugadores.values(),
        key=lambda x: (
            x["diferencia"],
            x["pg"],
            x["jugador"],
        ),
    )

    with col1:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="titulo">
                    Mejor % de victorias
                </div>
                <div class="nombre">
                    {escape(mejor_pct["jugador"])}
                </div>
                <div class="detalle">
                    {mejor_pct["pct_victorias"]:.1f}%
                    ({mejor_pct["pg"]}/{mejor_pct["pj"]})
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="titulo">
                    Más victorias
                </div>
                <div class="nombre">
                    {escape(mas_victorias["jugador"])}
                </div>
                <div class="detalle">
                    {mas_victorias["pg"]}
                    victorias en
                    {mas_victorias["pj"]}
                    partidas
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="titulo">
                    Mejor diferencia de puntos
                </div>
                <div class="nombre">
                    {escape(mejor_dif["jugador"])}
                </div>
                <div class="detalle">
                    {mejor_dif["diferencia"]:+d} puntos
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Parejas
    # -----------------------------------------------------------------------

    if stats_parejas:
        st.markdown("<br>", unsafe_allow_html=True)
        titulo_seccion("La fuerza de jugar juntos", "ESTADÍSTICAS POR PAREJA")

        cp1, cp2 = st.columns(2)

        # Mejor porcentaje.
        # En caso de empate: mayor número de partidas.
        mejor_pareja = max(
            stats_parejas.values(),
            key=lambda x: (
                x["pct_victorias"],
                x["pj"],
                x["pg"],
                x["pareja"],
            ),
        )

        # Peor porcentaje.
        # En caso de empate: mayor número de partidas.
        peor_pareja = min(
            stats_parejas.values(),
            key=lambda x: (
                x["pct_victorias"],
                -x["pj"],
                -x["pg"],
                x["pareja"],
            ),
        )

        with cp1:
            st.markdown(
                f"""
                <div class="mini-card">
                    <div class="titulo">
                        Mejor pareja
                    </div>
                    <div class="nombre">
                        {escape(mejor_pareja["pareja"])}
                    </div>
                    <div class="detalle">
                        {mejor_pareja["pct_victorias"]:.1f}%
                        ({mejor_pareja["pg"]}/{mejor_pareja["pj"]})
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with cp2:
            st.markdown(
                f"""
                <div class="mini-card">
                    <div class="titulo">
                        Pareja con margen de mejora
                    </div>
                    <div class="nombre">
                        {escape(peor_pareja["pareja"])}
                    </div>
                    <div class="detalle">
                        {peor_pareja["pct_victorias"]:.1f}%
                        ({peor_pareja["pg"]}/{peor_pareja["pj"]})
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ===========================================================================
# VISTA: JUGADORES
# ===========================================================================

def mostrar_jugadores(
    partidas_procesadas,
    stats_jugadores,
):
    if not stats_jugadores:
        mensaje_vacio(
            "No hay estadísticas de jugadores todavía."
        )
        return

    nombres = sorted(stats_jugadores.keys())

    # -----------------------------------------------------------------------
    # Buscador de jugadores
    # -----------------------------------------------------------------------

    busqueda = st.text_input(
        "🔎 Buscar jugador",
        placeholder="Escribe parte del nombre...",
        key="jugadores_busqueda",
    ).strip().casefold()

    jugadores_filtrados = [
        nombre
        for nombre in nombres
        if busqueda in nombre.casefold()
    ]

    lista = [
        stats_jugadores[nombre]
        for nombre in jugadores_filtrados
    ]

    st.markdown(
        "#### Tabla de estadísticas individuales"
    )

    df = tabla_jugadores_df(lista)

    if df.empty:
        mensaje_vacio(
            "No hay jugadores que coincidan con la búsqueda."
        )
    else:
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
        )

    # -----------------------------------------------------------------------
    # Ranking
    # -----------------------------------------------------------------------

    st.markdown("---")
    st.markdown("#### 🏆 Ranking")

    criterio_label = st.selectbox(
        "Ordenar ranking por",
        [
            "Mayor % de victorias",
            "Mayor número de victorias",
            "Mayor diferencia de puntos",
            "Nombre (A-Z)",
        ],
        key="jugadores_ranking_criterio",
    )

    criterio_map = {
        "Mayor % de victorias": "pct_victorias",
        "Mayor número de victorias": "victorias",
        "Mayor diferencia de puntos": "diferencia",
        "Nombre (A-Z)": "nombre",
    }

    stats_para_ranking = {
        nombre: stats_jugadores[nombre]
        for nombre in jugadores_filtrados
    }

    ranking = crear_ranking(
        stats_para_ranking,
        criterio_map[criterio_label],
    )

    if ranking:
        df_rank = pd.DataFrame(
            [
                {
                    "Posición": r["posicion"],
                    "Jugador": r["jugador"],
                    "PJ": r["pj"],
                    "PG": r["pg"],
                    "PP": r["pp"],
                    "% Victorias": f'{r["pct_victorias"]:.1f}%',
                }
                for r in ranking
            ]
        )

        st.dataframe(
            df_rank,
            width="stretch",
            hide_index=True,
        )
    else:
        mensaje_vacio()

    # -----------------------------------------------------------------------
    # Compañeros
    # -----------------------------------------------------------------------

    st.markdown("---")
    st.markdown("#### 🤝 Compañeros")

    companeros = calcular_companeros(
        partidas_procesadas
    )

    for jugador in jugadores_filtrados:
        info = companeros.get(jugador)

        with st.expander(f"👤 {jugador}"):

            if not info:
                mensaje_vacio(
                    f"{jugador} todavía no tiene partidas "
                    f"válidas con compañero."
                )
                continue

            cc1, cc2, cc3 = st.columns(3)

            mv = info["mas_victorias"]
            mp = info["mayor_pct_victorias"]
            md = info["mas_derrotas"]

            with cc1:
                st.markdown(
                    f"""
                    <div class="mini-card">
                        <div class="titulo">
                            🏅 Pareja con más victorias
                        </div>
                        <div class="nombre">
                            {escape(mv["companero"])}
                        </div>
                        <div class="detalle">
                            {mv["pg"]} victorias ·
                            {mv["pct_victorias"]:.1f}% juntos
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with cc2:
                st.markdown(
                    f"""
                    <div class="mini-card">
                        <div class="titulo">
                            📊 Mayor % de victorias
                        </div>
                        <div class="nombre">
                            {escape(mp["companero"])}
                        </div>
                        <div class="detalle">
                            {mp["pct_victorias"]:.1f}% ·
                            {mp["pj"]} partidas juntos
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with cc3:
                st.markdown(
                    f"""
                    <div class="mini-card">
                        <div class="titulo">
                            📉 Pareja con más derrotas
                        </div>
                        <div class="nombre">
                            {escape(md["companero"])}
                        </div>
                        <div class="detalle">
                            {md["pp"]} derrotas ·
                            {md["pct_derrotas"]:.1f}%
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ===========================================================================
# VISTA: PAREJAS
# ===========================================================================

def mostrar_parejas(stats_parejas):
    if not stats_parejas:
        mensaje_vacio(
            "No hay estadísticas de parejas todavía."
        )
        return

    # -----------------------------------------------------------------------
    # Buscador por texto, sin distinguir mayúsculas/minúsculas
    # -----------------------------------------------------------------------

    busqueda = st.text_input(
        "🔎 Buscar pareja",
        placeholder="Escribe parte del nombre de la pareja...",
        key="parejas_busqueda",
    ).strip().casefold()

    lista = [
        stats
        for stats in stats_parejas.values()
        if busqueda in stats["pareja"].casefold()
    ]

    df = tabla_parejas_df(lista)

    if df.empty:
        mensaje_vacio(
            "No hay parejas que coincidan con la búsqueda."
        )
    else:
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
        )


# ===========================================================================
# VISTA: PARTIDAS
# ===========================================================================

def mostrar_partidas(partidas_procesadas):
    validas = [
        p for p in partidas_procesadas
        if not p["empate"]
    ]

    if not validas:
        mensaje_vacio(
            "No hay partidas válidas todavía."
        )
        return

    jugadores_disp = sorted(
        {
            j
            for p in validas
            for j in (
                p["jugadores1"] + p["jugadores2"]
            )
        }
    )

    parejas_disp = sorted(
        {
            p["pareja1"]
            for p in validas
        }
        |
        {
            p["pareja2"]
            for p in validas
        },
        key=lambda k: pareja_nombre(*k),
    )

    mapa_parejas = {
        pareja_nombre(*k): k
        for k in parejas_disp
    }

    nombres_parejas = sorted(
        mapa_parejas.keys()
    )

    fechas_validas = [
        p["fecha"]
        for p in validas
    ]

    min_fecha = min(fechas_validas)
    max_fecha = max(fechas_validas)

    # -----------------------------------------------------------------------
    # Inicialización robusta de filtros:
    # todos seleccionados desde el principio
    # -----------------------------------------------------------------------

    if "part_jugadores" not in st.session_state:
        st.session_state["part_jugadores"] = jugadores_disp.copy()

    if "part_parejas" not in st.session_state:
        st.session_state["part_parejas"] = nombres_parejas.copy()

    if "part_desde" not in st.session_state:
        st.session_state["part_desde"] = min_fecha.date()

    if "part_hasta" not in st.session_state:
        st.session_state["part_hasta"] = max_fecha.date()

    if "part_busqueda" not in st.session_state:
        st.session_state["part_busqueda"] = ""

    # -----------------------------------------------------------------------
    # Limpiar filtros
    # -----------------------------------------------------------------------

    if st.button(
        "🧹 Limpiar filtros",
        key="part_limpiar",
    ):
        st.session_state["part_jugadores"] = jugadores_disp.copy()
        st.session_state["part_parejas"] = nombres_parejas.copy()
        st.session_state["part_desde"] = min_fecha.date()
        st.session_state["part_hasta"] = max_fecha.date()
        st.session_state["part_busqueda"] = ""
        st.rerun()

    # -----------------------------------------------------------------------
    # Filtros
    # -----------------------------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:
        f_jugadores = st.multiselect(
            "🔍 Jugadores mostrados (quita los que no quieras ver)",
            options=jugadores_disp,
            key="part_jugadores",
        )

    with col2:
        f_parejas_nombres = st.multiselect(
            "🔍 Parejas mostradas (quita las que no quieras ver)",
            options=nombres_parejas,
            key="part_parejas",
        )

    col3, col4 = st.columns(2)

    with col3:
        f_desde = st.date_input(
            "Fecha desde",
            key="part_desde",
            format="DD/MM/YYYY",
        )

    with col4:
        f_hasta = st.date_input(
            "Fecha hasta",
            key="part_hasta",
            format="DD/MM/YYYY",
        )

    # -----------------------------------------------------------------------
    # Buscador de texto de las partidas
    # -----------------------------------------------------------------------

    f_busqueda = st.text_input(
        "🔎 Buscar en partidas",
        placeholder="Jugador, pareja, resultado, ganador o fecha...",
        key="part_busqueda",
    ).strip().casefold()

    # -----------------------------------------------------------------------
    # Aplicar filtros
    # -----------------------------------------------------------------------

    partidas_filtradas = aplicar_filtros(
        partidas_procesadas,
        jugadores=set(f_jugadores),
        parejas={
            mapa_parejas[n]
            for n in f_parejas_nombres
        },
        fecha_desde=(
            datetime.combine(
                f_desde,
                datetime.min.time(),
            )
            if f_desde
            else None
        ),
        fecha_hasta=(
            datetime.combine(
                f_hasta,
                datetime.max.time(),
            )
            if f_hasta
            else None
        ),
    )

    # -----------------------------------------------------------------------
    # Buscador textual
    # -----------------------------------------------------------------------

    if f_busqueda:
        partidas_filtradas = [
            p
            for p in partidas_filtradas
            if f_busqueda
            in " ".join(
                [
                    p["fecha_str"],
                    pareja_nombre(*p["jugadores1"]),
                    pareja_nombre(*p["jugadores2"]),
                    f'{p["puntos1"]} - {p["puntos2"]}',
                    pareja_nombre(
                        *(
                            p["jugadores1"]
                            if p["ganador"] == "equipo1"
                            else p["jugadores2"]
                        )
                    ),
                ]
            ).casefold()
        ]

    if not partidas_filtradas:
        mensaje_vacio(
            "No hay partidas que coincidan con los filtros seleccionados."
        )
        return

    # -----------------------------------------------------------------------
    # Tabla
    # -----------------------------------------------------------------------

    filas = []

    for p in sorted(
        partidas_filtradas,
        key=lambda x: x["fecha"],
    ):
        eq1 = pareja_nombre(*p["jugadores1"])
        eq2 = pareja_nombre(*p["jugadores2"])

        ganador = (
            eq1
            if p["ganador"] == "equipo1"
            else eq2
        )

        filas.append(
            {
                "Fecha": p["fecha_str"],
                "Equipo 1": eq1,
                "Resultado": f'{p["puntos1"]} - {p["puntos2"]}',
                "Equipo 2": eq2,
                "Ganador": f"🏆 {ganador}",
            }
        )

    df = pd.DataFrame(filas)

    def resaltar_ganador(row):
        estilos = [""] * len(row)

        idx_ganador = list(row.index).index(
            "Ganador"
        )

        estilos[idx_ganador] = (
            "background-color: rgba(141,229,194,0.10); "
            "font-weight: 700; "
            "color: #8de5c2;"
        )

        return estilos

    st.dataframe(
        df.style.apply(
            resaltar_ganador,
            axis=1,
        ),
        width="stretch",
        hide_index=True,
    )


# ===========================================================================
# VISTA: EVOLUCIÓN
# ===========================================================================

def mostrar_evolucion(
    partidas_procesadas,
    stats_jugadores,
    stats_parejas,
):
    validas = sorted(
        [
            p
            for p in partidas_procesadas
            if not p["empate"]
        ],
        key=lambda x: x["fecha"],
    )

    if not validas:
        mensaje_vacio(
            "No hay partidas válidas para mostrar la evolución."
        )
        return

    nombres = sorted(
        stats_jugadores.keys()
    )

    seleccionados = st.multiselect(
        "📈 Jugadores comparados (quita los que no quieras ver)",
        options=nombres,
        default=nombres,
        key="evolucion_jugadores",
    )

    if not seleccionados:
        mensaje_vacio(
            "Selecciona al menos un jugador para ver su evolución."
        )
        return

    # -----------------------------------------------------------------------
    # Preparar series por jugador
    # -----------------------------------------------------------------------

    series_pct = {}
    series_victorias = {}
    series_dif = {}

    for jugador in seleccionados:
        fechas = []
        pct_acum = []
        vict_acum = []
        dif_acum = []

        pj = 0
        pg = 0
        dif = 0

        for p in validas:
            if jugador in p["jugadores1"]:
                propios = p["puntos1"]
                rival = p["puntos2"]
                gano = p["ganador"] == "equipo1"

            elif jugador in p["jugadores2"]:
                propios = p["puntos2"]
                rival = p["puntos1"]
                gano = p["ganador"] == "equipo2"

            else:
                continue

            pj += 1
            dif += propios - rival

            if gano:
                pg += 1

            fechas.append(p["fecha"])

            pct_acum.append(
                round(
                    (pg / pj) * 100,
                    1,
                )
            )

            # SIEMPRE ENTEROS
            vict_acum.append(int(pg))

            dif_acum.append(int(dif))

        series_pct[jugador] = (
            fechas,
            pct_acum,
        )

        series_victorias[jugador] = (
            fechas,
            vict_acum,
        )

        series_dif[jugador] = (
            fechas,
            dif_acum,
        )

    # -----------------------------------------------------------------------
    # % victorias acumulado
    # -----------------------------------------------------------------------

    st.markdown(
        "#### % de victorias acumulado"
    )

    fig1 = go.Figure()

    for jugador, (fechas, valores) in series_pct.items():
        if fechas:
            fig1.add_trace(
                go.Scatter(
                    x=fechas,
                    y=valores,
                    mode="lines+markers",
                    name=jugador,
                    hovertemplate=(
                        "%{fullData.name}"
                        "<br>%{x|%d/%m/%Y}"
                        "<br>%{y:.1f}%"
                        "<extra></extra>"
                    ),
                )
            )

    fig1.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis_title="% Victorias",
        xaxis_title="Fecha",
        legend_title="Jugador",
        xaxis=dict(
            tickformat="%d/%m/%Y",
        ),
    )

    st.plotly_chart(
        estilizar_grafico(fig1),
        width="stretch",
        theme=None,
    )

    # -----------------------------------------------------------------------
    # Victorias acumuladas
    # -----------------------------------------------------------------------

    st.markdown(
        "#### Victorias acumuladas"
    )

    fig2 = go.Figure()

    for jugador, (fechas, valores) in series_victorias.items():
        if fechas:
            fig2.add_trace(
                go.Scatter(
                    x=fechas,
                    y=[int(v) for v in valores],
                    mode="lines+markers",
                    name=jugador,
                    hovertemplate=(
                        "%{fullData.name}"
                        "<br>%{x|%d/%m/%Y}"
                        "<br>%{y:.0f} victorias"
                        "<extra></extra>"
                    ),
                )
            )

    fig2.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Victorias",
        xaxis_title="Fecha",
        legend_title="Jugador",
        xaxis=dict(
            tickformat="%d/%m/%Y",
        ),
        yaxis=dict(
            dtick=1,
            tickformat=".0f",
            rangemode="tozero",
        ),
    )

    st.plotly_chart(
        estilizar_grafico(fig2),
        width="stretch",
        theme=None,
    )

    # -----------------------------------------------------------------------
    # Diferencia de puntos acumulada
    # -----------------------------------------------------------------------

    st.markdown(
        "#### Diferencia de puntos acumulada"
    )

    fig3 = go.Figure()

    for jugador, (fechas, valores) in series_dif.items():
        if fechas:
            fig3.add_trace(
                go.Scatter(
                    x=fechas,
                    y=valores,
                    mode="lines+markers",
                    name=jugador,
                    hovertemplate=(
                        "%{fullData.name}"
                        "<br>%{x|%d/%m/%Y}"
                        "<br>%{y:.0f} puntos"
                        "<extra></extra>"
                    ),
                )
            )

    fig3.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Diferencia de puntos",
        xaxis_title="Fecha",
        legend_title="Jugador",
        xaxis=dict(
            tickformat="%d/%m/%Y",
        ),
        yaxis=dict(
            tickformat=".0f",
        ),
    )

    st.plotly_chart(
        estilizar_grafico(fig3),
        width="stretch",
        theme=None,
    )

    # -----------------------------------------------------------------------
    # Comparativa de parejas
    # -----------------------------------------------------------------------

    if stats_parejas:
        st.markdown("---")
        st.markdown(
            "#### Comparativa de % de victorias entre parejas principales"
        )

        principales = sorted(
            stats_parejas.values(),
            key=lambda x: -x["pj"],
        )[:6]

        if principales:
            fig4 = go.Figure(
                go.Bar(
                    x=[
                        s["pareja"]
                        for s in principales
                    ],
                    y=[
                        s["pct_victorias"]
                        for s in principales
                    ],
                    marker_color="#8de5c2",
                    text=[
                        f'{s["pct_victorias"]:.1f}%'
                        for s in principales
                    ],
                    textposition="outside",
                )
            )

            fig4.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                yaxis_title="% Victorias",
                xaxis_title="Pareja",
            )

            st.plotly_chart(
                estilizar_grafico(fig4),
                width="stretch",
                theme=None,
            )


# ===========================================================================
# APLICACIÓN PRINCIPAL
# ===========================================================================

def main():
    inyectar_css()

    datos_raw = cargar_datos()

    partidas_procesadas = procesar_partidas(
        datos_raw
    )

    stats_jugadores = calcular_estadisticas_jugadores(
        partidas_procesadas
    )

    stats_parejas = calcular_estadisticas_parejas(
        partidas_procesadas
    )

    periodo = (
        f'{partidas_procesadas[0]["fecha_str"]} — {partidas_procesadas[-1]["fecha_str"]}'
        if partidas_procesadas else "Tu próxima partida empieza aquí"
    )
    st.markdown(
        f"""
        <div class="brand-bar">
            <div class="brand"><span class="brand-mark" aria-hidden="true">♠</span>Mus<em>Stats</em></div>
            <div class="brand-meta"><span class="status-dot" aria-hidden="true"></span>EL CLUB DE LA CUADRILLA</div>
        </div>
        <section class="hero" aria-labelledby="hero-title">
            <div class="hero-copy">
                <div class="eyebrow">Cada partida cuenta</div>
                <h1 id="hero-title">El mus se juega.<br><span class="hero-accent">La historia se mide.</span></h1>
                <p>Las victorias, las mejores parejas y esas rachas que dan que hablar.
                Toda la historia de la cuadrilla, en un solo lugar.</p>
                <div class="hero-meta"><span class="pill">{escape(periodo)}</span>
                <span class="pill gold">{len(partidas_procesadas)} partidas registradas</span></div>
            </div>
            <div class="card-art" aria-hidden="true">
                <div class="playing-card back"></div>
                <div class="playing-card front">A ♠<div class="suit">♠</div><div class="corner">A ♠</div></div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Resumen",
            "Jugadores",
            "Parejas",
            "Partidas",
            "Evolución",
        ]
    )

    with tab1:
        mostrar_dashboard(
            partidas_procesadas,
            stats_jugadores,
            stats_parejas,
        )

    with tab2:
        titulo_seccion("Los protagonistas", "RENDIMIENTO INDIVIDUAL")
        mostrar_jugadores(
            partidas_procesadas,
            stats_jugadores,
        )

    with tab3:
        titulo_seccion("Mejor, en pareja", "CONEXIONES QUE SUMAN")
        mostrar_parejas(
            stats_parejas,
        )

    with tab4:
        titulo_seccion("El archivo de la mesa", "EXPLORA CADA RESULTADO")
        mostrar_partidas(
            partidas_procesadas,
        )

    with tab5:
        titulo_seccion("Una historia en movimiento", "RENDIMIENTO A LO LARGO DEL TIEMPO")
        mostrar_evolucion(
            partidas_procesadas,
            stats_jugadores,
            stats_parejas,
        )

    st.markdown(
        '<footer class="app-footer"><span>♠ MusStats · El club de la cuadrilla</span>'
        '<span>Los empates no computan en las estadísticas de rendimiento.</span></footer>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()