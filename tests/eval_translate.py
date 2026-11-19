import sys

from backend.translate import translate

CASES = [
    {
        "name": "filler: you know",
        "en": "So, you know, I think we should finish the report today.",
        "checks": [("no 'आप जानते'", lambda hi: "जानते" not in hi)],
    },
    {
        "name": "filler: uh/um",
        "en": "Uh, so, um, can you send me the file?",
        "checks": [("no उह/उम", lambda hi: "उह" not in hi and "उम" not in hi)],
    },
    {
        "name": "entity: Google Meet",
        "en": "Please join the Google Meet.",
        "checks": [("keeps 'Google Meet'", lambda hi: "Google Meet" in hi)],
    },
    {
        "name": "entity: Asterisk",
        "en": "I'll share the Asterisk server details there.",
        "checks": [("keeps 'Asterisk'", lambda hi: "Asterisk" in hi)],
    },
    {
        "name": "time + meaning: tomorrow",
        "en": "Can we move the meeting to 5pm tomorrow?",
        "checks": [
            ("has 'शाम 5 बजे'", lambda hi: "शाम 5 बजे" in hi),
            ("not 'कल की …'", lambda hi: "कल की" not in hi),
            ("not 'ले जा'", lambda hi: "ले जा" not in hi),
        ],
    },
    {
        "name": "time: 9.30am",
        "en": "The delivery is due at 9.30am.",
        "checks": [("has 'सुबह'", lambda hi: "सुबह" in hi)],
    },
    {
        "name": "abbreviation: ETA",
        "en": "What's the ETA on the delivery?",
        "checks": [("ETA explained", lambda hi: "अनुमानित" in hi or "कब तक" in hi)],
    },
    {
        "name": "tone: casual",
        "en": "Hey dude, wanna grab lunch after this?",
        "checks": [("no formal आप", lambda hi: "आप" not in hi)],
    },
    {
        "name": "tone: formal",
        "en": "Could you kindly share the quarterly report with me?",
        "checks": [("uses आप", lambda hi: "आप" in hi)],
    },
    {
        "name": "ASR error: Howie",
        "en": "Hey Howie, what's up, how are you doing?",
        "checks": [("no 'हाउई'", lambda hi: "हाउई" not in hi)],
    },
        {
        "name": "real name kept: Rahul",
        "en": "Hey Rahul, how are you doing?",
        "checks": [("keeps राहुल", lambda hi: "राहुल" in hi)],
    },
    {
        "name": "real name kept: Howard",
        "en": "Hey Howard, what's up, how are you doing?",
        "checks": [("keeps Howard", lambda hi: any(
            name in hi for name in ["हावर्ड", "हॉवर्ड", "Howard"]))],
    },
]


def main(runs: int) -> None:
    total_pass = total = 0
    for case in CASES:
        passes = 0
        failed_examples = []
        for _ in range(runs):
            hi = translate(case["en"])
            ok = all(check(hi) for _, check in case["checks"])
            passes += ok
            if not ok:
                failed_examples.append(hi)
        total_pass += passes
        total += runs
        mark = "✅" if passes == runs else "❌"
        print(f"{mark} {passes}/{runs}  {case['name']}")
        if failed_examples:
            print(f"      e.g. {failed_examples[0]}")
    print(f"\nOverall: {total_pass}/{total} ({100 * total_pass / total:.0f}%)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)