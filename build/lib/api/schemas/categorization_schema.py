"""CategorizationSchema."""
# Third-Party Libraries
from marshmallow import fields, validate

# khulnasoft-lab Libraries
from api.schemas.base_schema import BaseSchema
from utils.categorization import CATEGORIES


class CategorizationSchema(BaseSchema):
    """DomainSchema."""

    domain_id = fields.Str()
    domain_name = fields.Str()
    is_external = fields.Boolean(dump_default=False)
    proxy = fields.Str()
    status = fields.Str(
        validate=validate.OneOf(
            ["new", "recategorize", "submitted", "verified", "burned"]
        )
    )
    category = fields.Str(
        validate=validate.OneOf([category for category in CATEGORIES])
    )
    categorize_url = fields.Str(allow_none=True)
    check_url = fields.Str(allow_none=True)
