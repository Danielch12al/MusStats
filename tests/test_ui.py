"""Smoke tests for the dashboard and its native Streamlit interactions."""

from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def start_app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def test_dashboard_renders_all_sections(self):
        app = self.start_app()
        self.assertEqual(
            [tab.label for tab in app.tabs],
            ["Resumen", "Jugadores", "Parejas", "Partidas", "Evolución"],
        )
        markup = "\n".join(item.value for item in app.markdown)
        self.assertIn("La historia se mide.", markup)
        self.assertIn("Así está la mesa", markup)
        self.assertIn("Últimas partidas", markup)
        self.assertEqual(len(app.get("plotly_chart")), 5)

    def test_search_and_ranking_controls(self):
        app = self.start_app()
        app.text_input(key="jugadores_busqueda").set_value("no-such-player-9481").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("No hay jugadores que coincidan" in m.value for m in app.markdown))
        app.text_input(key="jugadores_busqueda").set_value("").run()
        app.selectbox(key="jugadores_ranking_criterio").select("Mayor número de victorias").run()
        self.assertEqual(len(app.exception), 0)
        app.text_input(key="parejas_busqueda").set_value("no-such-pair-9481").run()
        self.assertTrue(any("No hay parejas que coincidan" in m.value for m in app.markdown))

    def test_match_filter_reset(self):
        app = self.start_app()
        app.text_input(key="part_busqueda").set_value("no-such-match-9481").run()
        self.assertTrue(any("No hay partidas que coincidan" in m.value for m in app.markdown))
        app.button(key="part_limpiar").click().run()
        self.assertEqual(app.text_input(key="part_busqueda").value, "")
        self.assertEqual(len(app.exception), 0)

    def test_empty_evolution_selection(self):
        app = self.start_app()
        app.multiselect(key="evolucion_jugadores").set_value([]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Selecciona al menos un jugador" in m.value for m in app.markdown))

    def test_empty_dataset(self):
        app = AppTest.from_string(
            'from unittest.mock import patch\n'
            'import app\n'
            'with patch.object(app, "cargar_datos", return_value=[]):\n'
            '    app.main()\n',
            default_timeout=30,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.tabs), 5)
        self.assertTrue(any("0 partidas registradas" in m.value for m in app.markdown))

    def test_html_names_are_escaped(self):
        app = AppTest.from_string(
            'from unittest.mock import patch\n'
            'import app\n'
            'fixture = [{"fecha": "01/09/2026", '
            '"equipo1": {"jugador1": "<b>Ana</b>", "jugador2": "Luis", "puntos": 40}, '
            '"equipo2": {"jugador1": "Eva", "jugador2": "Juan", "puntos": 20}}]\n'
            'with patch.object(app, "cargar_datos", return_value=fixture):\n'
            '    app.main()\n',
            default_timeout=30,
        ).run()
        self.assertEqual(len(app.exception), 0)
        markup = "\n".join(item.value for item in app.markdown)
        self.assertIn("&lt;b&gt;Ana&lt;/b&gt;", markup)
        self.assertNotIn("<b>Ana</b>", markup)


if __name__ == "__main__":
    unittest.main()