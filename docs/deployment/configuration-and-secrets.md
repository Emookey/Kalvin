# Configuration and Secret References

Status: **CURRENT precedence and reference contract; providers are PLANNED.**

## Configuration layers

Precedence from lowest to highest is:

1. repository-safe defaults;
2. deployment-profile configuration;
3. host-local non-secret configuration;
4. separately namespaced runtime-generated values for fields explicitly declared generated.

Secret references are orthogonal inputs, not a high-precedence configuration layer. A secret value cannot be replaced by a non-secret default. Runtime-generated values cannot override repository version locks, profile security policy, host role, state authority, backup class, exposure ceiling, or secret references.

A conflict at the same layer, an unknown key, a missing required value, or an attempt to weaken a protected field fails validation. `core` never falls back from a missing canonical variable to a legacy alias unless an enabled compatibility entry explicitly maps the value and both conflict and retirement behavior are defined.

## Host-local references

Public desired manifests use logical references such as `host-config-ref://inventory/core-primary`, not machine paths or addresses. The future resolver binds the logical reference to protected host-local material. The public schema defines the reference shape, not its backing provider.

## Secret references

The neutral reference form is:

```text
secret-ref://<provider>/<service>/<name>
```

It is an opaque identifier, never a value or provider credential. Future providers may resolve it from protected local files, environment injection, a system credential facility, or an external secret manager. Provider selection and mapping are host-local.

Rules:

- Git stores only requirement IDs and abstract references;
- each secret has an owning service and intended consumer identity;
- a service receives individual required values, never an entire secret hierarchy;
- secret material is not written into a resolved deployment record, log, readiness detail, or diagnostic bundle;
- a missing, unreadable, ambiguous, or over-broad reference blocks the dependent service;
- rotation and recovery are provider responsibilities coordinated through a reviewed platform procedure;
- backup credentials, application credentials, human identities, monitoring identities, and host-management credentials remain separate.

No provider, local secret path, environment file, or production template is implemented in Phase 4C.
