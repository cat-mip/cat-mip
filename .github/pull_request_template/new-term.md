---
name: New Term Proposal
description: Propose a new canonical term for the CAT-MIP registry
title: "[TERM] Your Term Name"
labels: ["term-proposal"]
assignees: []

body:
  - type: markdown
    attributes:
      value: |
        Thank you for proposing a new term! Please fill out all sections below.
        Use the `standards/template.yaml` as your base — copy it to `standards/drafts/your-term-name.yaml`.

  - type: input
    id: term
    attributes:
      label: Canonical Term
      description: The exact term (Title Case, singular)
      placeholder: e.g., Access Point
    validations:
      required: true

  - type: textarea
    id: definition
    attributes:
      label: Definition
      description: Clear, precise definition (Markdown allowed)
      placeholder: |
        An Access Point is a network device that...
    validations:
      required: true

  - type: textarea
    id: synonyms
    attributes:
      label: Synonyms
      description: Common alternatives (one per line)
      placeholder: |
        - AP
        - Wi-Fi AP
    validations:
      required: true

  - type: textarea
    id: relationships
    attributes:
      label: Relationships
      description: How this term relates to others (one per line)
      placeholder: |
        - Access Point isConnectedTo Switch
        - Access Point serves Endpoint
    validations:
      required: true

  - type: textarea
    id: prompt_examples
    attributes:
      label: Prompt Examples
      description: Real-world natural language prompts
      placeholder: |
        - List all access points at the Denver office
        - Restart the rooftop access point
    validations:
      required: true

  - type: textarea
    id: agent_execution
    attributes:
      label: Agent Execution
      description: |
        interpretation: (no trailing colon)
        actions: (one per line, start with -)
      placeholder: |
        interpretation: When a prompt refers to an "Access Point," the AI agent will
        actions:
          - Identify the specific access point(s)...
          - Retrieve configuration...
    validations:
      required: true

  - type: checkboxes
    id: checklist
    attributes:
      label: Checklist
      options:
        - label: Used `standards/template.yaml` as base
          required: true
        - label: Filename is Title Case with spaces (e.g., Access Point.yaml)
          required: true
        - label: All fields filled (no TODOs)
          required: true
        - label: No trailing colon in interpretation
          required: true
        - label: Single quotes for strings with colons
          required: true
        - label: Linked to discussion issue
          required: true

  - type: input
    id: discussion
    attributes:
      label: Discussion Issue
      description: Link to the GitHub discussion where this was agreed
      placeholder: https://github.com/cat-mip/cat-mip/discussions/123
    validations:
      required: true
---
