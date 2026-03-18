# How “fine-tuning” works for Perkins (plain English)

You don’t need to know ML to change how Perkins behaves. Here’s what you have and how to adjust it.

---

## What you have now (no training)

Perkins uses **Ollama** with a **custom model** named `perkins-ai`. That custom model is built from:

1. **Base model:** Qwen2.5 3B Instruct (the “brain”).
2. **A Modelfile** that adds:
   - **Instructions** (system prompt): “You are Perkins, you compare reports vs MPD, output discrepancies, drivers, recommendations…”
   - **Examples** (few-shot): one example of report + MPD → analysis.
   - **Settings:** temperature, context length.

So the model’s **weights are not changed**. Only the **instructions and examples** you send each time (and a couple of knobs) are “tuned.” That’s why it’s not really “fine-tuning” in the textbook sense—it’s **customization via prompt and parameters**.

---

## How to “tune” Perkins (change how it answers)

All of this is done by editing the **Modelfile** and rebuilding the custom model on the VPS.

### 1. Edit the Modelfile (on your computer or on the VPS)

File: **`Modelfile`** in the repo (at the root).

- **SYSTEM** block = the instructions the model always sees.  
  Change this to:
  - Use different wording (e.g. “Always mention ATA chapter”).
  - Add rules (“Never recommend deferring critical tasks”).
  - Change tone (more formal, more concise, etc.).
- **Example (few-shot)** inside SYSTEM = one full example of input → output.  
  Add or replace with real examples from your reports/MPD so the model copies that style and structure.
- **PARAMETER temperature** = how “creative” vs focused the answers are.  
  - `0.1–0.3` = more focused, repeatable (good for technical analysis).  
  - `0.4–0.7` = more varied wording.
- **PARAMETER num_ctx** = how much text the model can look at at once (e.g. 4096 or 8192).

So “fine-tuning” for you = **edit that Modelfile** (instructions + examples + temperature/context), then rebuild on the server (next section).

### 2. Apply changes on the VPS

After you edit the Modelfile (and push to git, or copy it to the server):

```bash
# SSH into the server
ssh -i ~/.ssh/perkins_vps root@72.62.175.45

# Go to the app
cd /root/perkins

# Get latest Modelfile (if you pushed from git)
git pull

# Rebuild the custom model (reads Modelfile, overwrites perkins-ai)
ollama create perkins-ai -f Modelfile

# Restart the app so it keeps using perkins-ai
systemctl restart perkins
```

After that, every new request uses the new instructions and parameters. No need to retrain anything.

---

## Quick reference: what to change for what

| You want… | What to do |
|-----------|------------|
| Different wording / tone | Edit the **SYSTEM** text in `Modelfile`. |
| More consistent structure | Add **more examples** (copy your real report + MPD + good analysis) into the SYSTEM block. |
| Stricter / more focused answers | Lower **temperature** (e.g. `0.2` → `0.1`). |
| Longer reports / more context | Increase **num_ctx** (e.g. `4096` → `8192`). |
| Different ATA/regulatory focus | Add sentences to SYSTEM (e.g. “Always cite EASA AMC when relevant.”). |

---

## What *real* fine-tuning would be (optional read)

**Real fine-tuning** = training the model’s weights on your own data (e.g. hundreds of report + MPD + analysis pairs). That would:

- Require a training pipeline (e.g. LoRA), not just Ollama.
- Need a lot of curated examples and more time and compute.
- Produce a new model file you could then run in Ollama.

For most use cases, **editing the Modelfile** (instructions + examples + temperature) is enough and is what we mean by “fine-tuning” in this project. If you later want to do real weight fine-tuning, we can outline that as a separate, advanced step.

---

## One-page checklist

1. Open **`Modelfile`** in the repo.
2. Change the **SYSTEM** text (instructions and/or examples).
3. Optionally change **PARAMETER temperature** or **num_ctx**.
4. Save, push to git (or copy Modelfile to the VPS).
5. On VPS: `cd /root/perkins && git pull && ollama create perkins-ai -f Modelfile && systemctl restart perkins`.
6. Try a report in the chat; repeat from step 2 until you’re happy.

That’s it. You’re “fine-tuning” by editing the Modelfile and rebuilding.
