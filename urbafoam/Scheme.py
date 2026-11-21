def setup_scheme(scheme_cfg):
    return {
        'gradLimit_U': scheme_cfg.gradLimit_U,
        'gradLimit_p': scheme_cfg.gradLimit_p,
        'gradLimit_k': scheme_cfg.gradLimit_k,
        'gradLimit_epsilon': scheme_cfg.gradLimit_eps,
    }
