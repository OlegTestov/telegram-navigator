"""Custom exceptions."""


class ContentTableError(Exception):
    pass


class FetchError(ContentTableError):
    pass


class ClassificationError(ContentTableError):
    pass


class DatabaseError(ContentTableError):
    pass


class TOCError(ContentTableError):
    pass
