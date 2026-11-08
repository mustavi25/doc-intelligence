INVOICE_TOOL = {
    "name": "record_invoice",
    "description": "Record the invoice fields found in the document. Use null for anything not explicitly present.",
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_number": {"type": ["string", "null"]},
            "invoice_date": {"type": ["string", "null"], "description": "ISO format YYYY-MM-DD"},
            "supplier_name": {"type": ["string", "null"]},
            "customer_name": {"type": ["string", "null"]},
            "subtotal": {"type": ["number", "null"]},
            "tax": {"type": ["number", "null"]},
            "total": {"type": ["number", "null"]},
            "currency": {"type": ["string", "null"], "description": "ISO 4217 code, e.g. USD"},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": ["string", "null"]},
                        "quantity": {"type": ["number", "null"]},
                        "unit_price": {"type": ["number", "null"]},
                        "amount": {"type": ["number", "null"]},
                    },
                },
            },
            "source_snippets": {
                "type": "object",
                "description": "For each non-null scalar field, the exact text copied from the document that supports it.",
                "additionalProperties": {"type": "string"},
            },
            "uncertain_fields": {
                "type": "array", "items": {"type": "string"},
                "description": "Names of fields you are not confident about.",
            },
        },
        "required": ["invoice_number", "invoice_date", "supplier_name", "customer_name",
                     "subtotal", "tax", "total", "currency", "line_items", "source_snippets"],
    },
}