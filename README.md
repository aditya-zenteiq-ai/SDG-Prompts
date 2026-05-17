# SDG Prompts Repository

This repository serves as the central registry for all prompt templates and rotation configurations used across the Synthetic Data Generation (SDG) pipelines. 

## Repository Structure

### 1. Mid-Training Prompts (`Mid-Training/`)
Prompts designed for continuous, long-form narrative generation, reasoning, and conceptual extraction.

*   **Domain-Specific/Cooking/**
    *   `C9_immersive_narrative_rewriting.txt`
    *   `C10_translation.txt`
    *   `Rotation Conditions/cooking_rotation_variables.json`
*   **General/Dense_CoT/**
    *   `basic_cot_reasoning.txt`
*   **General/Dense_QA/**
    *   `dense_qa.txt`
*   **General/Rephrasing/**
    *   `rephrasing_prompt.txt`
*   **concept_extraction_expansion/**
    *   `analogy_generation/teacher.md`
    *   `causal_chain_analysis/teacher.md`
    *   `concept_application/teacher.md`
    *   `contrast_and_comparision/teacher.md`
    *   `extract_concept/teacher.md`
    *   `misconception_correction/teacher.md`
    *   `pairwise_relation_analysis/teacher.md`
    *   `qa_concept_level/teacher.md`
    *   `qa_pair_level/teacher.md`

### 2. Supervised Fine-Tuning (SFT) Prompts (`SFT/`)
Highly structured reasoning, instruction-following, and dialogue generation prompts.

*   **Domain-Specific/Cooking/**
    *   **Reasoning_and_Instruction_Following/**
        *   `C1_ingredient_substitution.txt`
        *   `C2_failure_diagnosis.txt`
        *   `C3_workflow_optimization.txt`
        *   `C4_flavor_profile_pairing.txt`
        *   `C5_recipe_scaling.txt`
        *   `C6_zero_waste_scraps.txt`
        *   `C11_regional_traditions.txt`
        *   `C12_festive_meal_plan.txt`
        *   `C13_preservation_guide.txt`
        *   `C14_ayurvedic_and_nutritional_annotations.txt`
    *   **Conversational_QA/**
        *   `C7_multi_turn_dialogue.txt`
        *   `C8_recipe_faq.txt`
    *   **Rotation Conditions/**
        *   `cooking_rotation_variables.json`

*   **Domain-Specific/Household/**
    *   **Reasoning_and_Instruction_Following/**
        *   `H1_appliance_troubleshooting.txt`
        *   `H2_plumbing_first_response.txt`
        *   `H3_electrical_safety_repair.txt`
        *   `H4_stain_surface_cleaning.txt`
        *   `H5_preventive_maintenance_schedule.txt`
        *   `H6_household_budget_planning.txt`
        *   `H7_home_safety_protocol.txt`
        *   `H8_fabric_laundry_care.txt`
        *   `H9_space_organisation_storage.txt`
        *   `H11_two_wheeler_maintenance.txt`
        *   `H12_monsoon_proofing_checklist.txt`
        *   `H13_lpg_cylinder_safety.txt`
        *   `H14_indian_first_aid.txt`
        *   `H15_material_based_maintenance.txt`
        *   `H16_regional_climate_adaptation.txt`
        *   `H17_jugaad_engineering.txt`
        *   `H20_resource_constraint_planning.txt`
    *   **Conversational_QA/**
        *   `H10_life_skill_repair_dialogue.txt`
        *   `H18_age_group_life_skill.txt`
        *   `H19_inprocess_troubleshooting_dialogue.txt`

### 3. Pipeline Prompts (`Pipeline Prompts/`)
Internal model instructions for auditing, factual verification, and guardrails.

*   `auditor/auditor.txt` (Correctness evaluation)
*   `dean/dean.txt` (Factual accuracy cross-referencing)
*   `guardrail/final_guardrail.txt` (Safety symmetry notes)
*   `initial_safety/initial_safety.txt` (Brand, leak, and abuse checks)