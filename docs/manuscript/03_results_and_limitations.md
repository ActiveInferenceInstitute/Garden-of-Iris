# Results and limitations

The repository supports three observable layers: user interaction, tagged record preparation, and operations that consume those records. A prediction tag records the intent of an entry. Linking a prediction to subsequent outcomes would require an explicit pairing rule and an independent check of the later evidence. Similarly, a fine-tuning-oriented export records a preparation step, with training and evaluation remaining separate tasks.

The experimental TensorFlow sketch and external model integrations have different provenance from the offline parsing and formatting utilities. The local gate documents syntax, documentation, and test surfaces, plus a separate model configuration lane. Reading those gates establishes which checks are available. It does not constitute a new run or a comparison between models.
