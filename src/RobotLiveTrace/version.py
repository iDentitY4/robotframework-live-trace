from importlib.metadata import metadata, version

_metadata = metadata("robotframework-live-trace")

VERSION = version("robotframework-live-trace")
AUTHOR = _metadata["Author"]
AUTHOR_EMAIL = _metadata["Author-email"]
DESCRIPTION = _metadata["Summary"]
