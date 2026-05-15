"""
Carvana domain adapter.

Wraps the existing URL builder and vehicle normalizer behind the DomainAdapter
interface so Carvana scraping works identically to any future generic domain.
"""

from domains.base import DomainAdapter, DomainConfig, FieldSchema
from domains.automotive.url_builder import build_search_url
from domains.automotive.normalizer import normalize_vehicle


AUTOMOTIVE_CONFIG = DomainConfig(
    domain_id="carvana_suvs",
    display_name="Carvana — SUVs",
    base_url="https://www.carvana.com/cars",
    pagination_style="query_param",
    pagination_param="page",
    max_pages=15,
    requires_js=True,
    fields=[
        FieldSchema("price",      "Price",      ["offers.price", "price", "listPrice"],              [], "float", "$",   required=True, is_primary_sort=True),
        FieldSchema("mileage",    "Mileage",    ["mileageFromOdometer", "mileage", "miles"],          [], "int",   "mi"),
        FieldSchema("year",       "Year",       ["modelDate", "year", "modelYear"],                  [], "int"),
        FieldSchema("trim",       "Trim",       ["trim", "trimLevel"],                               [], "str"),
        FieldSchema("vin",        "VIN",        ["vehicleIdentificationNumber", "vin"],              [], "str"),
        FieldSchema("drivetrain", "Drivetrain", ["driveWheelConfiguration", "driveType"],            [], "str"),
    ],
    scoring_weights={"price": 35, "mileage": 25, "age": 20, "shipping": 10, "hybrid": 10},
    system_prompt_context=(
        "You are an automotive analyst helping a buyer find the best used vehicle deal on Carvana."
    ),
    alert_on_new=True,
    alert_on_drop_pct=5.0,
)


class CarvanaAdapter(DomainAdapter):

    @property
    def domain_config(self) -> DomainConfig:
        return AUTOMOTIVE_CONFIG

    def build_url(self, page: int = 1, **filters) -> str:
        return build_search_url(
            make=filters.get("make", ""),
            model=filters.get("model", ""),
            min_year=filters.get("min_year", 0),
            max_year=filters.get("max_year", 9999),
            page=page,
            fuel_type=filters.get("fuel_type"),
        )

    def normalize(self, raw: dict, strategy: str, make: str = "", model: str = "") -> dict | None:
        return normalize_vehicle(raw, make, model, strategy)
