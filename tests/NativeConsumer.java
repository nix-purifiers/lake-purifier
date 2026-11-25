import java.lang.foreign.*;
import static java.lang.foreign.ValueLayout.JAVA_INT;
public class NativeConsumer {
  public static void main(String[] args) throws Throwable {
    var symbols=SymbolLookup.libraryLookup(args[0], Arena.global());
    var linker=Linker.nativeLinker();
    var initialize=linker.downcallHandle(symbols.find("projection_initialize").orElseThrow(),FunctionDescriptor.of(JAVA_INT));
    var answer=linker.downcallHandle(symbols.find("projection_answer").orElseThrow(),FunctionDescriptor.of(JAVA_INT,JAVA_INT));
    if ((int)initialize.invokeExact()!=1) throw new AssertionError();
    for(int i=0;i<100;++i) if((int)answer.invokeExact(i)!=i+41) throw new AssertionError();
    if((int)answer.invokeExact(-1)!=40) throw new AssertionError();
    System.out.println("Java FFM Lean allocation and exported UInt32 ABI PASS");
  }
}
