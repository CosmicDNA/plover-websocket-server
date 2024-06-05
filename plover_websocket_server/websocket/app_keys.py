from aiohttp.web import AppKey


def create_app_key(key_string):
    return {key_string: AppKey(key_string, str)}


def create_app_keys_from_list(key_strings):
    app_keys = {}
    for key in key_strings:
        app_keys.update(create_app_key(key))
    return app_keys


keys_to_create = ["websockets"]
app_keys = create_app_keys_from_list(keys_to_create)
