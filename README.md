# Household Knowledge Language

Household Knowledge Language is an evidence-aware data model for preserving not only what a household owns, but why it matters, where it came from, how it changed, who is connected to it, and how confidently each part of the story is known.

Traditional household inventories answer:

> What is this, and where is it?

Household Knowledge Language is designed to answer:

> Why does this matter?  
> Who gave it to us?  
> What changed over time?  
> What evidence supports the story?  
> What remains disputed or unknown?  
> Who is permitted to see the answer?

## The problem

A household contains more than objects. It contains gifts, inheritances, collections, family traditions, photographs, documents, memories, and ordinary items that became meaningful through use.

Most inventory systems preserve the object while losing the story.

This project explores how structured records can preserve:

- Identity and description
- Provenance and family meaning
- Current and historical location
- Relationships among people, objects, events, and collections
- Change over time
- Evidence supporting each claim
- Explicit uncertainty
- Privacy and human authority

## Evidence and uncertainty

The model distinguishes among:

- **Known** — supported as established within the record
- **Reported** — attributed to a person or source
- **Inferred** — derived from available evidence
- **Disputed** — materially conflicting accounts remain
- **Unknown** — the information is not currently known

Unknown is a valid result. The system should not invent a clean story merely because information is missing.

## Human authority

Software may organize evidence, identify conflicts, and help retrieve information.

It may not independently declare family truth, reduce privacy restrictions, or approve a family record.

Approval remains a human decision.

## How it works

A Household Knowledge Language record connects structured household information with evidence, uncertainty, relationships, change over time, privacy, and human authority.

The repository currently contains:

- `household_record.schema.json` — the generalized record model
- `ceramic_bird.json` — a fully fictional example record
- `validate_record.py` — validates a record against the schema
- `test_validate_record.py` — regression tests for core model rules
- `requirements.txt` — Python dependency definition
- `.github/workflows/validate.yml` — automatically runs validation on every change

## Example records

The repository includes three fictional records designed to test different kinds of household knowledge.

### 1. Blue Ceramic Bird

`ceramic_bird.json`

A single sentimental object with incomplete provenance.

It demonstrates:

- Known information supported by photographic evidence
- Reported family memory
- An explicitly unknown acquisition date
- Provenance and family meaning
- Evidence-linked questions and answers

### 2. Hallway Memory Shelf

`composite_memory_shelf.json`

A composite display made from several unrelated objects whose meaning comes from being displayed together.

It demonstrates:

- Nested household objects
- Mixed provenance
- Typed relationships
- Known, reported, inferred, and unknown claims
- Change over time
- Privacy boundaries within a public record

For example, the record may acknowledge that a sealed letter exists while refusing to expose its contents.

### 3. Annual Family Ornament Collection

`annual_ornament_collection.json`

A collection intended to contain one commemorative ornament for every year.

It demonstrates:

- Collection membership rules
- Year-by-year accumulation
- Seasonal storage and display
- Historical events
- Missing members
- Unresolved provenance

The collection currently has no confirmed 2017 ornament. The model distinguishes:

> No 2017 ornament is currently present.

from:

> A 2017 ornament never existed.

The first statement is supported by the inventory. The second is not known.

## What the three examples test

Together, the examples show that the same record language can represent:

**Object → Composite Display → Collection**

while preserving evidence, uncertainty, relationships, history, privacy, and human authority.

## Quick start

Install the validator dependency:

```bash
pip install -r requirements.txt

## Project status

This repository is an early public proof of concept.

The first public release will include:

- A generalized household-record JSON Schema
- A Python validator
- Fictional example records
- Governance and privacy tests
- Documentation of evidence and uncertainty

This repository will not contain real family records, private evidence, ChatGPT exports, medical information, financial information, or internal project-management files.
