import 'package:PiliPlus/grpc/bilibili/community/service/dm/v1.pb.dart';
import 'package:PiliPlus/utils/ios/pip_comments.dart';
import 'package:flutter_test/flutter_test.dart';

DanmakuElem comment(int time, int mode, {int weight = 5}) => DanmakuElem(
  progress: time,
  mode: mode,
  weight: weight,
  content: 'comment at $time',
  color: 0x12AB34,
);

void main() {
  test(
    'seek window includes its first comment and crosses segment boundaries',
    () {
      final packets = pipCommentPackets(
        [
          comment(359899, 1),
          comment(359900, 1),
          comment(360000, 1),
          comment(1079899, 1),
          comment(1079900, 1),
        ],
        positionMs: 359900,
        blockedTypes: {},
        minimumWeight: 0,
        blockColorful: false,
      );
      expect(packets.map((packet) => packet['time']), [359.9, 360.0, 1079.899]);
      expect(packets.first['text'], 'comment at 359900');
      expect(packets.first['color'], 0x12AB34);
    },
  );

  test('block settings apply to both scroll directions, top and bottom', () {
    final comments = [
      for (final mode in [1, 4, 5, 6, 7, 8]) comment(1000, mode),
    ];
    List<Object?> modes(Set<int> blocked) => pipCommentPackets(
      comments,
      positionMs: 0,
      blockedTypes: blocked,
      minimumWeight: 0,
      blockColorful: false,
    ).map((packet) => packet['mode']).toList();
    expect(modes({}), [1, 4, 5, 6]);
    expect(modes({2}), [4, 5]);
    expect(modes({4, 5}), [1, 6]);
    expect(modes({2, 4, 5}), isEmpty);
  });

  test(
    'weight threshold is inclusive and colorful blocking produces white text',
    () {
      final packets = pipCommentPackets(
        [
          comment(1000, 1, weight: 4),
          comment(1100, 1, weight: 5),
          comment(1200, 5, weight: 6),
        ],
        positionMs: 0,
        blockedTypes: {},
        minimumWeight: 5,
        blockColorful: true,
      );
      expect(packets.map((packet) => packet['time']), [1.1, 1.2]);
      expect(packets.map((packet) => packet['color']), [0xFFFFFF, 0xFFFFFF]);
    },
  );
}
