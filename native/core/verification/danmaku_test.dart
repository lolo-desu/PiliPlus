import 'package:test/test.dart';
import 'package:pili_native_core/v1.pb.dart';
import '../bin/bridge.dart';

void main() {
  test('unchanged upstream codec retains timing, mode, color and content',(){
    final message=DmSegMobileReply(elems:[DanmakuElem(progress:1250,mode:5,color:0x112233,content:'测试',fontsize:25)]);
    final decoded=decodeDanmaku(message.writeToBuffer()).single;
    expect(decoded['time'],1.25);expect(decoded['mode'],5);
    expect(decoded['color'],0x112233);expect(decoded['text'],'测试');
  });
  test('malformed data is an error, not an empty success',(){
    expect(()=>decodeDanmaku([0x0a,0xff]),throwsA(anything));
  });
}
