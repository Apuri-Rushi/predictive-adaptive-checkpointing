package ckpt.trace;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.zip.CRC32;

/** Deterministic hashing helpers (CRC-32 identical to Python zlib.crc32 on UTF-8 bytes). */
public final class Hashing {
    private Hashing() {
    }

    public static long crc32(String s) {
        CRC32 c = new CRC32();
        c.update(s.getBytes(StandardCharsets.UTF_8));
        return c.getValue();
    }

    public static int shardOf(String serial, int shards) {
        return (int) (crc32(serial) % shards);
    }

    public static String sha256(String text) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : d) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
