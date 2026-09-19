import 'dart:convert';
import 'dart:io';
import 'package:pili_native_core/v1.pb.dart';

List<Map<String,Object>> decodeDanmaku(List<int> bytes) =>
  DmSegMobileReply.fromBuffer(bytes).elems.map((e)=>{
    'time':e.progress/1000,'text':e.content,'mode':e.mode,'color':e.color,
    'id':e.id.toString(),'user':e.midHash,'size':e.fontsize,
  }).toList();

Future<void> main() async {
  await for(final line in stdin.transform(utf8.decoder).transform(const LineSplitter())) {
    try {
      final call=jsonDecode(line);
      if(call['method']!='danmaku.decode') throw FormatException('Unknown method');
      stdout.writeln(jsonEncode({'result':decodeDanmaku(base64Decode(call['data']))}));
    } catch(error) {stdout.writeln(jsonEncode({'error':error.toString()}));}
  }
}
