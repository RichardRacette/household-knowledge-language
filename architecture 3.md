# Architecture

The public proof of concept is intentionally small.

Its purpose is to demonstrate how household knowledge can be represented, validated, and tested without requiring a production database or user interface.

## Record model

A Household Knowledge Language record connects several kinds of information:

```text
Household Record
      │
      ├── Identity
      ├── Meaning
      ├── Provenance
      ├── Location / State
      │
      ├── Claims ───── Evidence
      │
      ├── Relationships
      ├── Events
      │
      ├── Questions & Answers
      │
      └── Privacy + Human Approval
```

### Identity

Describes what the record represents, such as an object, composite display, grouped record, or collection.

### Meaning

Preserves why the household keeps the item or collection and what significance it has.

### Provenance

Records how the object entered the household, who it came from, and how certain that history is.

### Location and state

Tracks where something is and whether it is displayed, stored, in use, transformed, or otherwise changed.

### Claims and evidence

Claims represent statements about the record. Evidence represents the sources supporting those statements.

The model keeps them separate so a future reader can inspect why a claim exists.

### Relationships

Typed relationships connect records to people, events, places, collections, and other records.

Examples include `CONTAINS`, `MEMBER_OF`, `GIVEN_BY`, `DISPLAYED_IN`, `STORED_IN`, and `ASSOCIATED_WITH_EVENT`.

### Events

Events preserve change over time, including acquisition, movement, display, repair, inheritance, transformation, and photography.

### Questions and answers

Records may include natural-language questions and evidence-aware answers.

Answer modes can include direct, qualified, unknown, private, or needs-human responses.

### Privacy and human approval

Privacy is part of the record model.

Human approval remains separate from technical validation.

A record can be structurally valid without being approved for public or family use.

## Public repository runtime

```text
JSON record
    ↓
household_record.schema.json
    ↓
validate_record.py
    ↓
test_validate_record.py
    ↓
GitHub Actions
```

- `household_record.schema.json` defines the public record structure.
- `validate_record.py` checks a JSON record against the schema.
- `test_validate_record.py` runs regression tests for important model rules.
- GitHub Actions runs the test suite and validates the fictional examples after every change to `main`.

## Example coverage

The initial public examples test three levels of household structure:

```text
Single Object
    ↓
Composite Display
    ↓
Collection
```

- `ceramic_bird.json` tests a single sentimental object.
- `composite_memory_shelf.json` tests nested objects and mixed privacy.
- `annual_ornament_collection.json` tests collection rules and unresolved membership gaps.

## What this architecture is not

The current public repository is not a production database, a family archive, a complete knowledge graph engine, an autonomous fact extractor, an automated approval system, or a public interface for real household records.

It is a deliberately small proof of concept for the record language and its governance principles.
