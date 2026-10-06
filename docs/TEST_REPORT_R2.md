# R2, WebP and upload quota verification

Validated on Python 3.12 with the dependencies in requirements.txt:

- 71 pytest tests passed, including the original authentication and three-role tests.
- New tests cover R2 permissions, cloud request parameters and signed URL expiry; missing objects; failed upload rollback and delete retry; legacy local photos; WebP format, compressed size, dimensions and metadata removal.
- Quota tests cover rate limits, storage capacity, concurrent SQLite reservations, daily and per-job limits, processing concurrency, read limits, usage endpoint authorization and persistence after restart.
- R2 failure tests confirm quota rejection before cloud calls, reservation retention after failed cleanup, and cleanup after a job assignment changes during upload.
- JavaScript syntax checked with node --check; offline preview regenerated.

R2 operations used an in-memory S3 double and botocore Stubber. No live bucket was created or tested. The Cloudflare dashboard requires login. Docker/Python 3.13 and production UI execution were not tested in this run.

One test dependency emitted a deprecation warning about AnyIO BlockingPortal. Tests passed.

These tests validate application controls, not a guarantee of zero Cloudflare charges. External bucket activity, compromised S3 keys and signed URL replay bypass application quotas.


Railway readiness update: the Docker bootstrap prepares a root-owned mounted
volume and drops to UID/GID 10001 before invoking run.py. The guide now includes
GitHub upload, Railway volume/settings/domain and initial admin setup. EU, US and
FedRAMP endpoint validation is covered. Latest suite: 76 passed, 1 skipped.
The real privilege-drop/volume ownership integration test was skipped because
this execution environment maps only UID 0. Two bootstrap tests passed; a Docker
container and an actual Railway deployment remain untested here.
