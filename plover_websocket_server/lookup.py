# Find the steno strokes for the given text
import re

from plover.engine import StenoEngine


class PloverLookupError(Exception):
    def __init__(self, msg, *args):
        self.msg = msg
        super().__init__(*args)


def lookup(engine: StenoEngine, text_to_lookup: str) -> list:
    """Recursively looks up a phrase by finding the longest possible dictionary match.

    Starts from the beginning of the string and then solving for the remainder.
    """
    memo = {}

    def get_steno_for_phrase(phrase: str) -> list | None:
        """Finds steno for a phrase.

        Handling capitalization by falling back
        to lowercase and prepending the capitalization stroke.
        """
        # 1. Try the phrase as-is (respecting capitalization)
        steno_capitalized: set = engine.reverse_lookup(phrase)

        # 2. Try the lowercase version and prepend cap stroke if needed
        steno_lowercase_modified = set()
        if phrase.lower() != phrase:
            steno_lowercase_raw = engine.reverse_lookup(phrase.lower())
            if steno_lowercase_raw:
                cap_next_results = ("KPA",)
                steno_lowercase_modified = {cap_next_results + s_lower for s_lower in steno_lowercase_raw}

        # Prioritize direct capitalized results
        combined = steno_capitalized.union(steno_lowercase_modified)
        if not combined:
            return None

        # Sort results: 1. Direct cap match, 2. Stroke count, 3. Key count
        return sorted(combined, key=lambda s: (s not in steno_capitalized, len(s), sum(len(p) for p in s)))

    def solve(words_tuple: tuple) -> list[list[tuple]]:
        if not words_tuple:
            return [[]]  # Base case: one valid solution, which is empty.
        if words_tuple in memo:
            return memo[words_tuple]

        def get_steno_options(i):
            return get_steno_for_phrase(" ".join(words_tuple[:i]))

        def process_i(i, best_steno_for_prefix):
            # Recursively find all solutions for the rest of the phrase
            suffix_tuple = words_tuple[i:]
            suffix_solutions = solve(suffix_tuple)

            # Combine the prefix's steno with each suffix solution
            return [[best_steno_for_prefix] + suffix_solution for suffix_solution in suffix_solutions]

        all_solutions = [
            solution
            for i in range(len(words_tuple), 0, -1)
            if (steno_options := get_steno_options(i))
            for solution in process_i(i, steno_options[0])
        ]

        memo[words_tuple] = all_solutions
        return all_solutions

    # Tokenize the input string, separating words from punctuation.
    # This finds sequences of word characters (\w+) or single non-word/non-space characters.
    words = re.findall(r"\w+|[^\w\s]", text_to_lookup)

    all_possible_sequences = solve(tuple(words))

    if not all_possible_sequences:
        return []

    # Sort the collected sequences by overall efficiency
    # 1. Total number of strokes in the sequence
    # 2. Total number of keys pressed in the sequence
    sorted_sequences = sorted(
        all_possible_sequences, key=lambda seq: (sum(len(stroke) for stroke in seq), sum(sum(len(p) for p in stroke) for stroke in seq))
    )

    return sorted_sequences
