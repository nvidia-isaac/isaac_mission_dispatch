bazel run //bzl:python_third_party.update
bazel run //bzl:python_third_party_linting.update
bazel mod deps --lockfile_mode=update 