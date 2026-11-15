import pytest

from app.bbox import parse_bbox

TIERRA_CALIENTE = "-101.5,18.4,-101.2,18.6"


# ---------- bbox ----------
def test_bbox_default_is_mexico():
    assert parse_bbox(None) == (-118.5, 14.0, -86.0, 33.5)


@pytest.mark.parametrize("raw", ["1,2,3", "a,b,c,d", "-100,20,-101,21", "-100,95,-99,96"])
def test_bbox_invalid(raw):
    with pytest.raises(ValueError):
        parse_bbox(raw)


@pytest.mark.parametrize("url", ["/trend?bbox=1,2,3", "/indicators?year=1999", "/compare?year_a=2010&year_b=2030"])
def test_invalid_params_return_422(client, url):
    assert client.get(url).status_code == 422


# ---------- meta ----------
def test_meta(client):
    m = client.get("/meta").json()
    assert m["default_year"] == 2025
    assert m["partial_years"] == [2000]
    assert m["complete_years"][0] == 2001 and len(m["complete_years"]) == 25
    assert m["estimated_years"] == list(range(2000, 2012))
    assert "FIRMS" in m["attribution"]


# ---------- tendencia / indicadores ----------
def test_trend_sums_peso_and_excludes_partial_year(client):
    t = client.get("/trend").json()
    act = {p["year"]: p["activity"] for p in t["series"]}
    assert act[2000] == 1000          # está en la serie...
    assert t["peak_year"] == 2005     # ...pero no puede ser el año pico (parcial)
    assert act[2005] == 50
    assert t["median_activity"] == 10  # mediana de 2001-2025, sin 2000
    assert act[2025] == 13             # 10 de abril + 3 de mayo


def test_indicators(client):
    i = client.get("/indicators?year=2025").json()
    assert i["activity"] == 13
    assert i["vs_median_pct"] == 30.0
    assert [m["month"] for m in i["top_months"]] == [4, 5]
    assert i["years_analyzed"] == 25
    assert i["estimated"] is False and i["partial"] is False
    assert client.get("/indicators?year=2005").json()["estimated"] is True


def test_indicators_default_year_is_latest(client):
    assert client.get("/indicators").json()["year"] == 2025


def test_bbox_filters_activity(client):
    # bbox sin actividad -> todo en cero, sin año pico
    i = client.get("/indicators?year=2025&bbox=-90,15,-89,16").json()
    assert i["activity"] == 0 and i["peak_year"] is None and i["vs_median_pct"] is None


def test_compare(client):
    c = client.get("/compare?year_a=2025&year_b=2005").json()
    assert c["a"]["year"] == 2025 and c["b"]["year"] == 2005
    assert c["delta"]["activity_abs"] == 37
    assert c["delta"]["activity_pct"] == pytest.approx(284.6)


BACKGROUND_BBOX = "-105.2,24.9,-104.9,25.2"  # solo la zona de fondo del conftest


def test_compare_basis_uses_activity_when_both_measured(client):
    b = client.get(f"/compare?year_a=2025&year_b=2020&bbox={BACKGROUND_BBOX}").json()["basis"]
    assert b["metric"] == "activity"
    assert (b["a"], b["b"]) == (13, 10)
    assert b["peak_years"] == [2025]


def test_compare_basis_is_harmonized_even_with_estimated_years(client):
    # Siempre actividad armonizada, aunque un año sea anterior a 2012
    b = client.get(f"/compare?year_a=2025&year_b=2005&bbox={BACKGROUND_BBOX}").json()["basis"]
    assert b["metric"] == "activity"
    assert (b["a"], b["b"]) == (13, 50)
    assert b["peak_years"] == [2005]
    assert b["pct_b_vs_a"] == pytest.approx(284.6)


def test_compare_basis_tie(client):
    b = client.get(f"/compare?year_a=2008&year_b=2002&bbox={BACKGROUND_BBOX}").json()["basis"]
    assert b["metric"] == "activity"
    assert b["peak_years"] == [2002, 2008]  # empate: 10 y 10


def test_compare_low_data_flag(client):
    # el conftest solo tiene detecciones crudas en 2020 -> pocos datos
    assert client.get("/compare?year_a=2025&year_b=2020").json()["basis"]["low_data"] is True


def test_calendar_shape(client):
    cal = client.get("/calendar").json()
    assert len(cal["values"]) == len(cal["years"]) == 26
    assert all(len(row) == 12 for row in cal["values"])
    assert cal["values"][cal["years"].index(2025)][3] == 10  # abril 2025
    assert cal["max"] == 1000


def test_report_bundles_everything(client):
    r = client.get(f"/report?year=2020&bbox={TIERRA_CALIENTE}").json()
    assert set(r) >= {"indicators", "trend", "calendar", "attribution", "methodology", "bbox"}


# ---------- mapa ----------
def test_hotspots_points_for_small_area(client):
    h = client.get(f"/hotspots?year=2020&bbox={TIERRA_CALIENTE}").json()
    assert h["mode"] == "points" and h["total_detections"] == 8
    f = h["points"]["features"][0]
    assert f["geometry"]["type"] == "Point" and set(f["properties"]) == {"datetime_utc", "satellite", "conf_level", "frp"}


def test_hotspots_grid_for_large_area(client):
    h = client.get("/hotspots?year=2020").json()  # 38 puntos > points_limit=10
    assert h["mode"] == "grid" and h["total_detections"] == 38
    assert sum(c[2] for c in h["grid"]["cells"]) == 38
    assert h["grid"]["columns"] == ["lat", "lon", "count", "frp_max"]


def test_hotspots_min_conf(client):
    h = client.get(f"/hotspots?year=2020&bbox={TIERRA_CALIENTE}&min_conf=high").json()
    assert h["total_detections"] == 3


def test_recurrent_zones_criterion(client):
    z = client.get("/recurrent-zones").json()
    # entran: la zona recurrente (16 años) y la de fondo (25 años con >=10 celdas-día)
    # no entran: la débil (4 celdas-día/año) ni la corta (14 años)
    assert z["total_polygons"] == 2
    rec = client.get("/recurrent-zones?bbox=-100.1,18.9,-99.9,19.1").json()["features"]
    assert len(rec) == 1
    props = rec[0]["properties"]
    assert props["years_active_max"] == 16 and props["first_year"] == 2001 and props["last_year"] == 2016
    assert client.get("/recurrent-zones?bbox=-99.1,19.9,-98.9,20.1").json()["features"] == []  # débil
    assert client.get("/recurrent-zones?bbox=-98.1,20.9,-97.9,21.1").json()["features"] == []  # corta
    assert client.get("/recurrent-zones?bbox=-105.1,24.9,-104.9,25.1").json()["features"][0]["properties"]["years_active_max"] == 25


def test_export_csv(client):
    r = client.get(f"/export/csv?year=2020&bbox={TIERRA_CALIENTE}")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("latitude,longitude,datetime_utc")
    assert len(lines) == 9  # encabezado + 8
    assert "attachment" in r.headers["content-disposition"]
    assert "FIRMS" in r.headers["x-attribution"]


def test_export_csv_empty_area_has_header_only(client):
    r = client.get("/export/csv?year=2020&bbox=-90,15,-89,16")
    assert r.text.strip().splitlines() == [r.text.strip()]
