import Batteries.Data.List.Basic
@[export projection_answer]
def answer (x : UInt32) : UInt32 :=
  let values := (List.range 42).map (fun n => n + x.toNat)
  (values.splitAtD 41 0).2.head!.toUInt32
