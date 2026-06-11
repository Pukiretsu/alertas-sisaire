"""Descarga de reportes CSV desde portal JSF/SISAIRE usando Playwright."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from air_quality_alerts.config import Settings

logger = logging.getLogger(__name__)


class SISAIREDownloader:
    """Automatiza navegación, consulta y descarga CSV desde un portal PrimeFaces/JSF."""

    def __init__(
        self,
        ids_estaciones: list[str],
        contaminante: str,
        fecha_ini: str,
        fecha_fin: str,
        ruta: str | os.PathLike = "./downloads",
        filename: str = "sisaire",
        headless: bool = True,
        target_url: str | None = None,
    ) -> None:
        self.ids_estaciones_consulta = [str(item) for item in ids_estaciones]
        self.contaminante = contaminante
        self.fecha_inicio = fecha_ini
        self.fecha_fin = fecha_fin
        self.ruta = Path(ruta)
        self.filename = filename
        self.headless = headless
        self.target_url = target_url or Settings.JSF_TARGET_URL

    def start_download(self) -> Path:
        """Ejecuta la descarga y retorna la ruta del CSV descargado."""
        if not self.target_url:
            raise ValueError("Debe configurar JSF_TARGET_URL en .env o pasarlo como parámetro.")

        self.ruta.mkdir(parents=True, exist_ok=True)
        output_path = self.ruta / f"reporte-{self.filename}.csv"

        with sync_playwright() as playwright:
            executable_path = Settings.CHROMIUM_EXECUTABLE_PATH
            browser_kwargs = {"headless": self.headless}
            if executable_path and Path(executable_path).exists():
                browser_kwargs["executable_path"] = executable_path

            browser = playwright.chromium.launch(**browser_kwargs)
            context = browser.new_context(accept_downloads=True)
            context.set_default_timeout(Settings.PLAYWRIGHT_DEFAULT_TIMEOUT_MS)
            self._block_irrelevant_content(context)
            page = context.new_page()

            try:
                logger.info("Navegando al portal: %s", self.target_url)
                page.goto(self.target_url, wait_until="networkidle")
                self._wait_until_loaded(page)
                self._select_estaciones(page)
                self._select_contaminante(page)
                self._select_fechas(page)
                self._select_timeframe(page)
                self._consultar(page)
                self._download_csv(page, output_path)
                return output_path
            finally:
                browser.close()

    # Nombre anterior conservado para no romper imports existentes.
    def start_scrapping(self) -> Path:  # noqa: D401
        """Alias de compatibilidad para start_download."""
        return self.start_download()

    def _block_irrelevant_content(self, context) -> None:
        recursos_ignorar = {"image", "font", "media"}

        def interceptar(route):
            if route.request.resource_type in recursos_ignorar:
                route.abort()
            else:
                route.continue_()

        context.route("**/*", interceptar)

    def _wait_until_loaded(self, page: Page) -> None:
        page.wait_for_timeout(300)
        for selector in ['i[id="loading"]', 'i[id="loadingResults"]', ".ui-blockui"]:
            locator = page.locator(selector)
            try:
                if locator.count() and locator.first.is_visible():
                    locator.first.wait_for(state="hidden", timeout=30000)
            except PlaywrightTimeoutError:
                logger.warning("Timeout esperando ocultar loader: %s", selector)

        js_check = "() => typeof PrimeFaces === 'undefined' || PrimeFaces.ajax.Queue.isEmpty()"
        page.wait_for_function(js_check, timeout=60000)

    def _select_estaciones(self, page: Page) -> None:
        self._wait_until_loaded(page)
        selector_dropdown = 'div[id="filtroForm:estacionesSel"]'
        page.locator(selector_dropdown).click()
        panel = page.locator('div[id="filtroForm:estacionesSel_panel"]')
        panel.wait_for(state="visible")

        for estacion_id in self.ids_estaciones_consulta:
            item = panel.locator(f'li[data-item-value="{estacion_id}"]')
            item.wait_for(state="visible")
            checkbox = item.locator(".ui-chkbox-box")
            checkbox.click()

        page.locator(selector_dropdown).click()
        logger.info("Estaciones seleccionadas: %s", len(self.ids_estaciones_consulta))
        self._wait_until_loaded(page)

    def _select_contaminante(self, page: Page) -> None:
        if not self.contaminante:
            return
        selector_dropdown = 'div[id="filtroForm:contaminanteSel"]'
        page.locator(selector_dropdown).click()
        panel = page.locator('div[id="filtroForm:contaminanteSel_panel"]')
        panel.wait_for(state="visible")
        item = panel.locator(f'li[data-label="{self.contaminante}"]')
        item.wait_for(state="visible")
        item.click()
        self._wait_until_loaded(page)

    def _select_fechas(self, page: Page) -> None:
        for selector, valor in [
            ('input[id="filtroForm:fechaIni_input"]', self.fecha_inicio),
            ('input[id="filtroForm:fechaFin_input"]', self.fecha_fin),
        ]:
            input_el = page.locator(selector)
            input_el.wait_for(state="visible")
            input_el.click()
            input_el.fill("")
            input_el.press_sequentially(valor, delay=40)
            input_el.press("Tab")
            page.wait_for_timeout(300)
        self._wait_until_loaded(page)

    def _select_timeframe(self, page: Page) -> None:
        page.locator('div[id="filtroForm:tipoSel"]').click()
        panel = page.locator('div[id="filtroForm:tipoSel_panel"]')
        panel.wait_for(state="visible")
        # Opción horaria. Ajustable si el portal cambia los IDs.
        panel.locator('li[id="filtroForm:tipoSel_1"]').click()
        self._wait_until_loaded(page)

    def _consultar(self, page: Page) -> None:
        page.locator('button[id="filtroForm:btnConsultar"]').click()
        self._wait_until_loaded(page)

    def _download_csv(self, page: Page, output_path: Path) -> None:
        selector_csv = 'a .fa-file-text-o'
        with page.expect_download(timeout=60000) as download_info:
            page.locator(selector_csv).click()
        download = download_info.value
        download.save_as(output_path)
        logger.info("CSV descargado en: %s", output_path)


# Alias de compatibilidad con el nombre original del proyecto.
SISAIREscrapper = SISAIREDownloader


if __name__ == "__main__":
    ids_estaciones_consulta = [
        "29586",
        "31877",
        "8249",
        "31862",
        "8254",
        "8243",
        "31867",
        "31866",
        "31865",
        "31860",
        "31869",
        "31805",
        "31807",
        "31863",
        "31864",
        "29617",
        "30040",
        "32089",
        "31953",
        "31870",
        "8250",
        "31952",
        "8252",
    ]

    downloader = SISAIREDownloader(
        ids_estaciones=ids_estaciones_consulta,
        contaminante="PM2.5",
        fecha_ini="2023-01-01",
        fecha_fin="2023-01-02",
        ruta="./downloads",
        filename="TEST_REFAC",
        headless=False,
    )
    downloader.start_download()
