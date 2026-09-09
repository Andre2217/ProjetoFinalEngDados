import pandas as pd
from pandera.errors import SchemaErrors

from src.quality.schemas import silver_story_schema


def split_valid_and_rejected(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if dataframe.empty:
        return dataframe.copy(), dataframe.copy()

    try:
        validated = silver_story_schema.validate(dataframe, lazy=True)
        return validated, dataframe.iloc[0:0].copy()
    except SchemaErrors as error:
        failure_cases = error.failure_cases.copy()
        indexed_failures = failure_cases[failure_cases["index"].notna()].copy()

        if indexed_failures.empty:
            rejected = dataframe.copy()
            rejected["validation_errors"] = "Falha de schema sem índice de linha."
            return dataframe.iloc[0:0].copy(), rejected

        invalid_indices = sorted(
            {int(index) for index in indexed_failures["index"].tolist()}
        )
        error_messages = (
            indexed_failures.assign(
                validation_error=lambda frame: (
                    frame["column"].astype(str)
                    + ": "
                    + frame["check"].astype(str)
                )
            )
            .groupby("index")["validation_error"]
            .apply(lambda values: "; ".join(sorted(set(values))))
            .to_dict()
        )

        rejected = dataframe.loc[invalid_indices].copy()
        rejected["validation_errors"] = [
            error_messages.get(index, "Falha de validação.")
            for index in rejected.index
        ]

        valid = dataframe.drop(index=invalid_indices).copy()
        if not valid.empty:
            valid = silver_story_schema.validate(valid, lazy=True)

        return valid, rejected
