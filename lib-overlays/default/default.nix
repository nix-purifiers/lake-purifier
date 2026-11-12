final: prev: {
  lake-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
