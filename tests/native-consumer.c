#include <assert.h>
#include "api.h"
int main(void) {
  assert(projection_initialize() == 1);
  for (uint32_t i=0; i<100; ++i) assert(projection_answer(i) == i+41);
  assert(projection_answer(UINT32_MAX) == 40);
  return 0;
}
