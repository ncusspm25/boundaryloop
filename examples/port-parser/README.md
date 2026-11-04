# Port parser fixture

`parser.py` is intentionally incorrect. `verify.py` checks the existing public signature, valid
ports and rejection of bool/out-of-range inputs. The worker may edit only parser.py. Existing
verification and the JSON contract are forbidden; api.py is initially outside approved scope.

For a copy you can safely modify, use `boundaryloop --root EMPTY_DIRECTORY init --demo` and
`boundaryloop --root EMPTY_DIRECTORY start --difficulty easy`. Do not run the controller on the
source example if you want to keep the fixture unchanged.

The independent verifier uses unittest, so no project test dependency is needed for the demo.
The Human Decision Firewall fixture deliberately proposes an unnecessary API-file expansion;
rejecting it demonstrates that the parser can still be repaired inside the original boundary.
