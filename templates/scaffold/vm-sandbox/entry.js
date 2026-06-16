// Local rebuild entry. Load original target JS from source/ only after evidence is stable.
globalThis.__reverseLabEntry = function reverseLabEntry(input) {
  return {
    input,
    signature: "replace-with-target-signature",
  };
};
