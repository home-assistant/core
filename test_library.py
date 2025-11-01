#!/usr/bin/env python3
"""Quick test script for daybetter_python library."""

import asyncio
import sys

try:
    from daybetter_python import DayBetterClient
except ImportError:
    print("❌ daybetter_python library not installed!")
    print("Run: pip install daybetter-services-python==1.0.4")
    sys.exit(1)


async def test_library():
    """Test the library methods."""
    # 从 Home Assistant 配置中获取 token
    # 你需要替换成实际的 token
    token = input("请输入你的 token（从 .storage/core.config_entries 中获取）: ")
    
    if not token or token == "":
        print("❌ Token 不能为空！")
        return
    
    client = DayBetterClient(token=token)
    
    try:
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🔍 测试 API 方法")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        # Test 1: fetch_devices
        print("1️⃣  测试 fetch_devices()...")
        devices = await client.fetch_devices()
        print(f"   ✅ 返回 {len(devices)} 个设备")
        print(f"   数据: {devices}\n")
        
        # Test 2: fetch_pids
        print("2️⃣  测试 fetch_pids()...")
        pids = await client.fetch_pids()
        print(f"   ✅ 返回 PIDs: {pids}\n")
        
        # Test 3: fetch_device_statuses
        print("3️⃣  测试 fetch_device_statuses()...")
        statuses = await client.fetch_device_statuses()
        print(f"   ✅ 返回 {len(statuses)} 个状态")
        print(f"   数据: {statuses}\n")
        
        # Test 4: filter_sensor_devices
        print("4️⃣  测试 filter_sensor_devices()...")
        sensor_devices = client.filter_sensor_devices(devices, pids)
        print(f"   ✅ 过滤后 {len(sensor_devices)} 个传感器设备")
        print(f"   数据: {sensor_devices}\n")
        
        # Test 5: merge_device_status
        print("5️⃣  测试 merge_device_status()...")
        merged = client.merge_device_status(sensor_devices, statuses)
        print(f"   ✅ 合并后 {len(merged)} 个设备")
        print(f"   数据: {merged}\n")
        
        # Test 6: fetch_sensor_data (一次性方法)
        print("6️⃣  测试 fetch_sensor_data()...")
        sensor_data = await client.fetch_sensor_data()
        print(f"   ✅ 返回 {len(sensor_data)} 个传感器")
        print(f"   数据: {sensor_data}\n")
        
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ 所有测试完成！")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        if len(sensor_data) == 0:
            print("⚠️  警告: fetch_sensor_data() 返回空列表!")
            print("\n可能的原因:")
            print("  1. 没有传感器设备")
            print("  2. PIDs 中没有 'sensor' 类型")
            print("  3. 过滤逻辑有问题")
            print("\n请检查上面的输出，看看哪一步返回了空数据。")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()
        print("\n✅ 连接已关闭")


if __name__ == "__main__":
    asyncio.run(test_library())

