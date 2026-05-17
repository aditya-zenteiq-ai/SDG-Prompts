# Cooking Rotation Variables

This directory contains `cooking_rotation_variables.json`, which defines the compatibility matrix and exhaust strategy used to diversify the cooking synthetic data generation pipeline.

It provides lists for:
- Dietary Restrictions
- Audiences
- Serving Scales
- Indian Languages
- Indian Regions (with compatible festivals and preservation methods)

When the pipeline generates prompts, it substitutes variables like `{{ request.dietary }}` or `{{ request.audience }}` with items from this JSON configuration to ensure cultural and functional accuracy.
