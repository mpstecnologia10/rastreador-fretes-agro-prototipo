from pipeline.adapters import freteemtemporeal as ft, roduno


def test_listing_age_is_not_a_publication_date():
    html = """<a class="freight-card" href="https://freteemtemporeal.com.br/frete/1">
    <span class="freight-route-text">Campo Verde / MT</span>
    <span class="freight-route-text">Santos / SP</span>
    <span class="freight-time">4 dias</span></a>"""
    row, = ft.parse(html)
    assert row["data_local"] is None
    ft.apply_detail(row, "<p>Data: 03/03/2026</p>")
    assert row["data_local"] == "2026-03-03"


def test_sitemap_limits_distinct_mt_routes():
    entries = [f"<loc>https://roduno.com.br/fretes/rota/x-mt-para-y-{i}</loc>" for i in range(30)]
    routes = roduno.route_links("".join(entries + entries).encode())
    assert len(routes) == len(set(routes)) == 25
