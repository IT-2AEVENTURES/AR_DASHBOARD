import polars as pl

from app.config.constants import COL_AR_PERSON, COL_SALES_CODE


def clean_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Clean column names to lowercase snake_case."""
    cleaned_columns = []
    for column in df.columns:
        cleaned = str(column).lower().strip().replace(" ", "_").replace(".", "").replace("#", "id")
        cleaned_columns.append(cleaned)
    return df.rename(dict(zip(df.columns, cleaned_columns)))


def validate_mapping(raw_df: pl.DataFrame, mapping_df: pl.DataFrame) -> dict:
    """Validate that each sales code in the raw data has an AR assignment."""
    raw_sales_codes = raw_df[COL_SALES_CODE].drop_nulls().unique()
    mapped_sales_codes = mapping_df[COL_SALES_CODE].drop_nulls().unique()
    missing_codes = raw_sales_codes.filter(~raw_sales_codes.is_in(mapped_sales_codes)).to_list()

    return {
        "is_valid": len(missing_codes) == 0,
        "missing_codes": missing_codes,
    }
