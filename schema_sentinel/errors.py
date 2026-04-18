"""Custom exceptions for Schema Sentinel."""


class SchemaSentinelError(Exception):
    """Base exception for Schema Sentinel failures."""


class DatasetReadError(SchemaSentinelError):
    """Raised when a dataset cannot be loaded or validated."""


class ConfigurationError(SchemaSentinelError):
    """Raised when a configuration file cannot be loaded or parsed."""


class ComparisonError(SchemaSentinelError):
    """Raised when a comparison cannot be completed."""
