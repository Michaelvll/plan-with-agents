# Curator Notes: Database Schema Example

## What Made This Debate Interesting

Database design requires balancing normalization against query performance, with real cost implications.

## Key Trade-offs Discussed

1. **Normalization Level**: 3NF vs denormalized for read performance
2. **Index Strategy**: B-tree vs composite vs covering indexes
3. **Status Tracking**: Enum column vs separate history table

## Why This Example Is Valuable

- Shows quantitative analysis (query patterns, storage costs)
- Demonstrates how agents reason about future scale
- Illustrates concrete DDL output in consensus

## How to Use This Example

Run the original task to see how your multi-turn planning compares:
```bash
/plan-with-multi-turn planning "Design schema for e-commerce orders with indexing strategy"
```
