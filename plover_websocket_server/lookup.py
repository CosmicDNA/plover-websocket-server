# Find the steno strokes for the given text
import re

from plover import log
from plover.engine import StenoEngine


class PloverLookupError(Exception):
    def __init__(self, msg, *args):
        self.msg = msg
        super().__init__(*args)


def lookup(engine: StenoEngine, text_to_lookup: str) -> list:
    """Recursively looks up a phrase by finding the longest possible dictionary match.

    Starts from the beginning of the string and then solving for the remainder.

    A lookup can fail (return an empty list) if any part of the tokenized input
    string cannot be found in Plover's dictionaries. The lookup is performed
    recursively, and if any segment of the phrase has no corresponding steno
    strokes, the entire lookup for that path will fail, and if no alternative
    paths are found, the overall result will be empty.
    """
    memo = {}
    log.debug(f"Starting lookup for: '{text_to_lookup}'")

    def get_steno_for_phrase(phrase: str) -> list | None:
        """Finds steno for a phrase.

        Handling capitalization by falling back
        to lowercase and prepending the capitalization stroke.
        """
        # 1. Try the phrase as-is (respecting capitalization)
        log.debug(f"  - get_steno_for_phrase('{phrase}')")

        steno_capitalized: set = engine.reverse_lookup(phrase)

        # If the phrase is a single non-word character (like '!'),
        # also try looking it up as a Plover command (e.g., '{!}').
        if len(phrase) == 1 and not phrase.isalnum():
            # Handle characters that are special within Plover's command syntax
            command_phrase = f"{{{phrase}}}"
            log.debug(f"    - Trying command lookup for '{command_phrase}'")
            steno_from_command = engine.reverse_lookup(command_phrase)
            if steno_from_command:
                steno_capitalized.update(steno_from_command)

        # 2. Try the lowercase version and prepend cap stroke if needed
        steno_lowercase_modified = set()
        if phrase.lower() != phrase:
            steno_lowercase_raw = engine.reverse_lookup(phrase.lower())
            if steno_lowercase_raw:
                cap_next_results = ("KPA",)
                steno_lowercase_modified = {cap_next_results + s_lower for s_lower in steno_lowercase_raw}

        # Prioritize direct capitalized results
        combined = steno_capitalized.union(steno_lowercase_modified)
        numeric_phrase = re.sub(r"[$,€£]", "", phrase.replace(",", ""))
        if numeric_phrase.isdigit():
            digit_steno_list = []
            all_digits_found = True
            for digit in numeric_phrase:
                digit_steno = engine.reverse_lookup(digit)
                if not digit_steno:
                    all_digits_found = False
                    break
                digit_steno_list.append(min(digit_steno, key=len))  # Choose shortest steno for the digit
            if all_digits_found:
                combined_digit_steno = tuple(s for steno_tuple in digit_steno_list for s in steno_tuple)
                combined.add(combined_digit_steno)

        # If after all attempts, we have no results, return None.
        if not combined:
            # Only issue a warning for single words that are not found, as this is the root cause of failure.
            is_single_word = " " not in phrase
            if is_single_word:
                log.warning(f"Failed to find steno for word: '{phrase}'")
            else:
                log.debug(f"    - FAILED to find steno for phrase: '{phrase}'")
            return None

        # Sort results: 1. Direct cap match, 2. Stroke count, 3. Key count
        return sorted(combined, key=lambda s: (s not in steno_capitalized, len(s), sum(len(p) for p in s)))

    def solve(words_tuple: tuple) -> list[list[tuple]]:
        if not words_tuple:
            return [[]]  # Base case: one valid solution, which is empty.
        if words_tuple in memo:
            return memo[words_tuple]
        log.debug(f"--> solve({words_tuple})")

        def get_steno_options(i):
            return get_steno_for_phrase(" ".join(words_tuple[:i]))

        max_lookup_length = min(len(words_tuple), engine._dictionaries.longest_key)

        def process_i(i, best_steno_for_prefix):
            # Recursively find all solutions for the rest of the phrase
            prefix_phrase = " ".join(words_tuple[:i])
            suffix_tuple = words_tuple[i:]
            suffix_solutions = solve(suffix_tuple)

            # Combine the prefix's steno with each suffix solution
            return [[{"text": prefix_phrase, "steno": best_steno_for_prefix}] + suffix_solution for suffix_solution in suffix_solutions]

        all_solutions = [
            solution
            for i in range(max_lookup_length, 0, -1)
            if (steno_options := get_steno_options(i))
            for solution in process_i(i, steno_options[0])
        ]

        if not all_solutions:
            # This is the point of failure. It means for the current `words_tuple`,
            # no prefix could be found in the dictionary that also had a valid suffix solution.
            log.debug(f"  <-- solve({words_tuple}) -> FAILED: No steno found for any prefix.")
        memo[words_tuple] = all_solutions
        return all_solutions

    # Tokenize the input string, separating words from punctuation.
    # This finds sequences of word characters (including those with internal apostrophes)
    # currency symbols attached to numbers, numbers with commas, or single non-word/non-space characters.
    token_regex = r"[$€£]?\d+(?:,\d+)*|\w+(?:['’]\w+)*|[^\w\s]"  # nosec B105
    words = re.findall(token_regex, text_to_lookup)

    all_possible_sequences = solve(tuple(words))

    log.debug(f"All possible sequences: {all_possible_sequences}")

    if not all_possible_sequences:
        log.debug(f"Lookup failed for '{text_to_lookup}'. No valid steno sequence found.")
        return []

    # Sort the collected sequences by overall efficiency
    # 1. Total number of strokes in the sequence
    # 2. Total number of keys pressed in the sequence
    sorted_sequences = sorted(
        all_possible_sequences,
        key=lambda seq: (
            sum(len(item["steno"]) for item in seq),
            sum(sum(len(p) for p in item["steno"]) for item in seq),
        ),
    )

    log.debug(f"Lookup finished. Returning {sorted_sequences}")
    return sorted_sequences
