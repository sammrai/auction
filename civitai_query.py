import requests
import pandas as pd
from functools import lru_cache
from urllib.parse import quote

# https://wiki.civitai.com/wiki/Civitai_API#GET_/api/v1/models

@lru_cache(maxsize=128)
def fetch_civitai_models(query: str) -> pd.DataFrame:
    """
    Fetches models from the CivitAI API based on the query and returns a DataFrame.

    Args:
        query (str): The search query for the API.

    Returns:
        pd.DataFrame: A DataFrame containing model details.
    """
    # API URL
    encoded_query = quote(query)
    url = f"https://civitai.com/api/v1/models?query={encoded_query}&limit=10&nsfw=true"
    
    # params = {
    #     "query": query,
    #     "limit": 10,
    #     "nsfw": True,
    # }
    # Fetch data from the API
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}")

    data = response.json()

    # Extract relevant data for the DataFrame
    models = data.get("items", [])
    df_data = [
        {
            "id": int(model.get("id")),
            "name": model.get("name"),
            # "description": model.get("description", ""),
            "allowNoCredit": model.get("allowNoCredit"),
            "allowCommercialUse": model.get("allowCommercialUse", []),
            "allowDerivatives": model.get("allowDerivatives"),
            "allowDifferentLicense": model.get("allowDifferentLicense"),
            "type": model.get("type"),
            "minor": model.get("minor"),
            "poi": model.get("poi"),
            "nsfw": model.get("nsfw"),
            "nsfwLevel": model.get("nsfwLevel"),
            "downloadCount": model["stats"].get("downloadCount") if "stats" in model else None,
            # "thumbsUpCount": model["stats"].get("thumbsUpCount") if "stats" in model else None,
            # "thumbsDownCount": model["stats"].get("thumbsDownCount") if "stats" in model else None,
        }
        for model in models
    ]

    # Create and return a DataFrame
    return pd.DataFrame(df_data)

if __name__ == "__main__":
    
    fetch_civitai_models("Rokudenashi Style")
    fetch_civitai_models("Amazing Embeddings - fcNegative + fcPortrait suite")

# Example usage:
# model_json = fetch_civitai_model_by_name("Granblue Fantasy PSXL | Illustrious/Pony Style Lora")
# print(model_json)


# Example usage:
# model_json = fetch_civitai_model_by_name("pony", "Granblue Fantasy PSXL | Illustrious/Pony Style Lora")
# print(model_json)



# Example usage:
# df = fetch_civitai_models("pony")
# Display the DataFrame
# import ace_tools as tools; tools.display_dataframe_to_user(name="CivitAI Models for 'pony'", dataframe=df)
