import 'package:PiliPlus/grpc/bilibili/community/service/dm/v1.pb.dart';

/// Build timestamped native packets after account/rule filtering by the loader.
List<Map<String, Object?>> pipCommentPackets(
  Iterable<DanmakuElem> comments, {
  required int positionMs,
  required Set<int> blockedTypes,
  required int minimumWeight,
  required bool blockColorful,
}) => [
  for (final comment in comments)
    if (comment.progress >= positionMs &&
        comment.progress < positionMs + 720000 &&
        comment.weight >= minimumWeight &&
        (comment.mode == 1 ||
            comment.mode == 4 ||
            comment.mode == 5 ||
            comment.mode == 6) &&
        !(comment.mode == 4
            ? blockedTypes.contains(4)
            : comment.mode == 5
            ? blockedTypes.contains(5)
            : blockedTypes.contains(2)))
      <String, Object?>{
        'time': comment.progress / 1000,
        'text': comment.content,
        'color': blockColorful ? 0xFFFFFF : comment.color,
        'mode': comment.mode,
      },
];
