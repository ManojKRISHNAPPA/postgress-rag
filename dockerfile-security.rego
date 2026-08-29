package main

import future.keywords.in

##############################
# Secrets
##############################

secrets_env = {
    "passwd",
    "password",
    "pass",
    "secret",
    "key",
    "access",
    "api_key",
    "apikey",
    "token",
    "tkn"
}

# Do not store secrets in ENV variables
deny contains msg if {
    input[i].Cmd == "env"

    val := input[i].Value

    some item in val
    some secret in secrets_env

    contains(lower(item), secret)

    msg := sprintf(
        "Line %d: Potential secret in ENV key found: %s",
        [i, item]
    )
}


##############################
# Trusted Base Images
##############################

trusted_registries = {
    "docker.io",
    "ghcr.io",
    "public.ecr.aws"
}

# Only use trusted base images
deny contains msg if {
    input[i].Cmd == "from"

    image := input[i].Value[0]
    parts := split(image, "/")

    count(parts) > 1

    registry := lower(parts[0])

    not registry in trusted_registries

    msg := sprintf(
        "Line %d: Base image uses an untrusted registry: %s",
        [i, image]
    )
}


##############################
# No latest tag
##############################

deny contains msg if {
    input[i].Cmd == "from"

    image := lower(input[i].Value[0])

    endswith(image, ":latest")

    msg := sprintf(
        "Line %d: Do not use 'latest' tag for base images: %s",
        [i, image]
    )
}


##############################
# Avoid curl/wget bashing
##############################

deny contains msg if {
    input[i].Cmd == "run"

    val := concat(" ", input[i].Value)

    regex.match(
        "(curl|wget)[^|>]*(\\||>)",
        lower(val)
    )

    msg := sprintf(
        "Line %d: Avoid curl/wget bashing",
        [i]
    )
}


##############################
# Do not upgrade packages
##############################

warn contains msg if {
    input[i].Cmd == "run"

    val := concat(" ", input[i].Value)

    regex.match(
        ".*\\b(apk|yum|dnf|apt|pip)\\b.*\\b(install|upgrade|update|dist-upgrade)\\b.*",
        lower(val)
    )

    msg := sprintf(
        "Line %d: Do not upgrade system packages: %s",
        [i, val]
    )
}


##############################
# Prefer COPY over ADD
##############################

deny contains msg if {
    input[i].Cmd == "add"

    msg := sprintf(
        "Line %d: Use COPY instead of ADD",
        [i]
    )
}


##############################
# USER must be specified
##############################

any_user if {
    input[i].Cmd == "user"
}

deny contains msg if {
    not any_user

    msg := "Do not run as root, use USER instead"
}


##############################
# Do not run as root
##############################

forbidden_users = {
    "root",
    "toor",
    "0"
}

deny contains msg if {
    input[i].Cmd == "user"

    user_value := lower(input[i].Value[0])

    user_value in forbidden_users

    msg := sprintf(
        "Line %d: USER directive (USER %s) is forbidden",
        [i, user_value]
    )
}


##############################
# Do not use sudo
##############################

deny contains msg if {
    input[i].Cmd == "run"

    val := concat(" ", input[i].Value)

    contains(lower(val), "sudo")

    msg := sprintf(
        "Line %d: Do not use 'sudo' command",
        [i]
    )
}


##############################
# Multi-stage build
##############################

default multi_stage = false

multi_stage = true if {
    input[i].Cmd == "copy"

    some flag in input[i].Flags

    startswith(lower(flag), "--from=")
}


# Warn if COPY exists but no multi-stage build is detected
warn contains msg if {
    multi_stage == false

    some i
    input[i].Cmd == "copy"

    msg := "COPY is used, but the Dockerfile does not appear to use a multi-stage build"
}