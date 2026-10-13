"""Local evidence-linked scope review. Similarity suggests; people decide."""
import os
import re
from pathlib import Path

MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
THRESHOLD = 0.40
MARGIN = 0.08
UNITS = {'page', 'email', 'round', 'hour', 'item'}


def validate_rows(rows, name):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
        raise ValueError(f'{name}: provide 1–20 rows.')
    result = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f'{name} row {i}: invalid row.')
        text = row.get('text')
        if not isinstance(text, str) or not 3 <= len(text.strip()) <= 500:
            raise ValueError(f'{name} row {i}: description must be 3–500 characters.')
        quantity = row.get('quantity')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 1000:
            raise ValueError(f'{name} row {i}: quantity must be a whole number from 1 to 1000.')
        unit = row.get('unit')
        if unit not in UNITS:
            raise ValueError(f'{name} row {i}: choose a supported unit.')
        result.append({'id': f'{name[0].upper()}{i}', 'text': text.strip(), 'quantity': quantity, 'unit': unit})
    return result


def lexical_ranking(query, texts):
    tokens = lambda x: set(re.findall(r'[a-z]+', x.lower()))
    q = tokens(query)
    return sorted(range(len(texts)), key=lambda i: -len(q & tokens(texts[i])) / max(1, len(q | tokens(texts[i]))))


class Reviewer:
    def __init__(self, cache=None):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(MODEL, revision=REVISION, device='cpu',
            cache_folder=cache or os.environ.get('BRIEF_LEDGER_CACHE', str(Path.home()/'.cache/brief-ledger')),
            trust_remote_code=False, local_files_only=os.environ.get('HF_HUB_OFFLINE') == '1')

    def analyze(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('Provide a brief and requests.')
        brief = validate_rows(payload.get('brief'), 'brief')
        requests = validate_rows(payload.get('requests'), 'requests')
        texts = [r['text'] for r in brief + requests]
        if any(len(t) > self.model.max_seq_length for t in self.model.tokenizer(texts, truncation=False)['input_ids']):
            raise ValueError('A description exceeds the model token limit; shorten it rather than silently truncating.')
        vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        scores = vectors[len(brief):] @ vectors[:len(brief)].T
        results = []
        for request, similarities in zip(requests, scores):
            ranked = sorted(range(len(brief)), key=lambda i: -float(similarities[i]))
            top = ranked[0]
            best = float(similarities[top])
            gap = best - float(similarities[ranked[1]]) if len(ranked) > 1 else best
            signal = 'No clear match' if best < THRESHOLD else ('Ambiguous match' if gap < MARGIN else 'Related deliverable')
            candidate = brief[top]
            comparable = signal == 'Related deliverable' and candidate['unit'] == request['unit']
            delta = request['quantity'] - candidate['quantity'] if comparable else None
            if not comparable:
                quantity_note = 'Compare manually: uncertain match or different units.'
            elif delta > 0:
                quantity_note = f'Requested total is {delta} {candidate["unit"]}(s) above the agreed total.'
            elif delta == 0:
                quantity_note = 'Same stated quantity; wording, revisions and exclusions still need review.'
            else:
                quantity_note = 'Requested total is below the agreed total; review the actual work.'
            results.append({'request': request, 'signal': signal, 'score': round(best, 4),
                'margin': round(gap, 4), 'quantity_delta': delta, 'quantity_note': quantity_note,
                'candidates': [{'source': brief[i], 'score': round(float(similarities[i]), 4)} for i in ranked[:3]]})
        return {'brief': brief, 'results': results, 'model': MODEL, 'revision': REVISION,
            'threshold': THRESHOLD, 'margin_threshold': MARGIN,
            'notice': 'Similarity is not approval, contract interpretation, or proof that work is included. Review every row.'}
