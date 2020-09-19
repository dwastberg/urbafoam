from .Config import get_or_update_config


def setup_scheme(config):
    config_group = "urbafoam.scheme"

    scheme_data = {}
    scheme_data['gradLimit_U'] = get_or_update_config(config, config_group, "gradLimit_U", 1)
    scheme_data['gradLimit_p'] = get_or_update_config(config, config_group, "gradLimit_p", 1)
    scheme_data['gradLimit_k'] = get_or_update_config(config, config_group, "gradLimit_k", 1)
    scheme_data['gradLimit_epsilon'] = get_or_update_config(config, config_group, "gradLimit_eps", 1)

    return scheme_data
