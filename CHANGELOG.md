# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Subcollection support via `Settings.parent` with optional `parent=` on CRUD methods.
- `_parent_path` tracking for subcollection instances.
- Recursive cascade deletes with `delete(cascade=True)`.
- `collection_group_find()` for cross-parent queries.
- `subcollection()` convenience accessor and `SubCollectionAccessor` helper.
- Comprehensive subcollection test coverage.

### Changed
- `_build_query()` now resolves collection paths for subcollections and returns `(query, resolved_parent_path)`.
- `batch_write()` resolves collection paths for top-level and subcollection models.

### Fixed
- N/A
