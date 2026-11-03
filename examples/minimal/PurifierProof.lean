import Aesop

theorem proofSymmetry (a b : Nat) (h : a = b) : b = a := by aesop

def answer : Nat := 42

theorem answerCorrect : answer = 42 := by decide
