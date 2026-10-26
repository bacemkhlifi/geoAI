# GeoAI evidence-quality update

This branch preserves the existing `/v1/site-analysis` request and response fields and adds canonical crop IDs, category, conditional status, missing inputs, rule score and model version. The Express adapter also accepts the currently deployed 0.5 response, so the Python deployment is independent.

Changes: ten complete calendar years; explicit coverage/finite-value checks; missing rain cannot become zero; modeled/reanalysis provenance; bounded one-day climate cache; consistent ERA5 source (the tested ERA5-Land response lacked precipitation); sanitized provider failures; unique report IDs; pH screening; low-water-reliability caps; diagnostic actions separated from crops; low confidence retained until field validation.

Run `python -m unittest discover -s tests -v`. No production data or service configuration is changed by tests. Deploying and calibrating these rules is separate from testing them. Plant profiles remain provisional, not a validated yield model. Climate cache is per process, so multiple workers maintain separate bounded caches.
